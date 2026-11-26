import datetime
import math
import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables, query as q
import pycountry
from pycountry_convert import country_alpha2_to_continent_code
from country_state_city import Country, State, City
from geopy.geocoders import Nominatim
from .MapUserModule import get_authenticated_user_row

geolocator = Nominatim(user_agent="NaturistMappingProject")

MAX_RENDER_MARKERS = 400
USER_LIST_CLUSTER_COLOR = '#9370DB'
DEFAULT_ZOOM_BOUNDS = {
    'south': 32.0,
    'north': 42.5,
    'west': -125.0,
    'east': -114.0,
}


def get_target_table(use_test_table):
    """Helper to return the correct Data Table based on the flag."""
    return app_tables.mapitems_test if use_test_table else app_tables.mapitems


def generate_coded_datetime_id(dt=None):
    """Generates a sortable integer ID in YYYYMMDDHHMMSS format (UTC)."""
    ts = dt or datetime.datetime.now(datetime.timezone.utc)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=datetime.timezone.utc)
    else:
        ts = ts.astimezone(datetime.timezone.utc)
    return int(ts.strftime("%Y%m%d%H%M%S"))


def get_region_from_country_code(country_code):
    """Maps a country code to a global region using pycountry_convert."""
    if not country_code:
        return "Other"
    try:
        continent_code = country_alpha2_to_continent_code(country_code.strip().upper())
        continent_map = {
            "NA": "North America",
            "SA": "South America",
            "EU": "Europe",
            "AS": "Asia",
            "AF": "Africa",
            "OC": "Oceania"
        }
        return continent_map.get(continent_code, "Other")
    except Exception:
        return "Other"


def calculate_haversine_distance_km(lat1, lon1, lat2, lon2):
    """Calculates great-circle distance between two points in kilometers."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon / 2) ** 2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def _viewport_width_in_unit(bounds, unit_type):
    """Returns east-west viewport width in miles or km for the given bounds."""
    if not bounds:
        return None
    try:
        north = float(bounds['north'])
        south = float(bounds['south'])
        east = float(bounds['east'])
        west = float(bounds['west'])
        mid_lat = (north + south) / 2.0
        width_km = calculate_haversine_distance_km(mid_lat, west, mid_lat, east)
        if unit_type in ['miles', 'mi']:
            return width_km / 1.60934
        return width_km
    except Exception:
        return None


def get_marker_color(count):
    """Determines marker hex color based on record/user count tiers."""
    if count <= 999:
        return '#ADD8E6'
    elif count <= 9999:
        return '#87CEEB'
    elif count <= 99999:
        return '#1E90FF'
    elif count <= 249999:
        return '#4169E1'
    elif count <= 999999:
        return '#0000CD'
    else:
        return '#000080'


def get_marker_scale(count):
    """Determines marker symbol scale based on record/user count tiers."""
    if count <= 999:
        return 8
    elif count <= 9999:
        return 10
    elif count <= 99999:
        return 12
    elif count <= 249999:
        return 16
    elif count <= 999999:
        return 18
    else:
        return 20


def _sanitize_coords(lat, lon, state=''):
    """Validates and normalizes latitude/longitude floats, returning (lat, lon) or None."""
    if lat is None or lon is None:
        return None
    try:
        lat_f = float(lat)
        lon_f = float(lon)
    except (ValueError, TypeError):
        return None

    if not (-90.0 <= lat_f <= 90.0):
        return None

    if 0.0 < lon_f <= 90.0:
        if (state or '').strip().upper() == 'CA':
            lon_f = -119.4179
        else:
            lon_f = -abs(lon_f)

    if not (-180.0 <= lon_f <= 180.0):
        return None

    return lat_f, lon_f


def _in_bounds(lat, lon, bounds):
    """Checks whether (lat, lon) falls inside a {'north','south','east','west'} dict."""
    if not bounds:
        return True
    north = bounds.get('north')
    south = bounds.get('south')
    east = bounds.get('east')
    west = bounds.get('west')

    if north is not None and lat > float(north):
        return False
    if south is not None and lat < float(south):
        return False

    if west is not None and east is not None:
        w, e = float(west), float(east)
        if w <= e:
            if not (w <= lon <= e):
                return False
        else:
            if not (lon >= w or lon <= e):
                return False
    return True


def _bbox_overlaps_point_radius(row, center_lat, center_lon, radius_km):
    """Checks if a postal summary row's center or bbox falls within radius_km of center."""
    plat = row.get('center_lat')
    plon = row.get('center_lon')
    if plat is None or plon is None:
        return False
    plat_f, plon_f = float(plat), float(plon)

    # Expand search window by ~0.5 deg (~55 km) for bbox overlap check
    lat_pad = max(0.5, (radius_km / 111.0) + 0.25)
    cos_lat = max(0.1, math.cos(math.radians(center_lat)))
    lon_pad = max(0.5, (radius_km / (111.0 * cos_lat)) + 0.25)

    min_lat = row.get('min_lat')
    max_lat = row.get('max_lat')
    min_lon = row.get('min_lon')
    max_lon = row.get('max_lon')

    if min_lat is not None and max_lat is not None and min_lon is not None and max_lon is not None:
        if (float(max_lat) < center_lat - lat_pad or
                float(min_lat) > center_lat + lat_pad or
                float(max_lon) < center_lon - lon_pad or
                float(min_lon) > center_lon + lon_pad):
            return False

    return calculate_haversine_distance_km(center_lat, center_lon, plat_f, plon_f) <= (radius_km + 15.0)


def _users_for_postal_pairs(postal_pairs):
    """Fetches distinct usernames from map_user_lookup for matching (country_code, postal_code) pairs."""
    users = set()
    lookup_table = app_tables.map_user_lookup
    for cc, pc in postal_pairs:
        filters = {'postal_code': pc}
        if cc:
            filters['country_code'] = cc
        try:
            for r in lookup_table.search(q.fetch_only('user'), **filters):
                u = r.get('user')
                if u:
                    users.add(u)
        except Exception:
            pass
    return users


def _zoom_tier_spec(zoom_level, focus_tier=None):
    """Determines clustering mode and grid cell size for the current zoom level."""
    z = None
    if zoom_level is not None:
        try:
            z = float(zoom_level)
        except (ValueError, TypeError):
            z = None

    if focus_tier == 'postal':
        return {'mode': 'postal', 'cell': None, 'tag': f'Z{z}:Postal'}

    if z is None or z <= 5:
        return {'mode': 'state', 'cell': None, 'tag': f'Z{z}:State'}
    elif z <= 7:
        return {'mode': 'grid', 'cell': 2.5, 'tag': f'Z{z}:SubRegion'}
    elif z <= 9:
        return {'mode': 'grid', 'cell': 0.8, 'tag': f'Z{z}:Metro'}
    elif z <= 11:
        return {'mode': 'grid', 'cell': 0.2, 'tag': f'Z{z}:CityBand'}
    else:
        if focus_tier == 'city':
            return {'mode': 'grid', 'cell': 0.05, 'tag': f'Z{z}:City'}
        return {'mode': 'postal', 'cell': None, 'tag': f'Z{z}:Postal'}


def _state_level_markers(bounds=None):
    """Returns one marker per state from map_state_summary."""
    fetch_cols = ('country_code', 'state', 'center_lat', 'center_lon', 'user_count')
    try:
        rows = list(app_tables.map_state_summary.search(q.fetch_only(*fetch_cols)))
    except Exception:
        rows = []

    markers = []
    for row in rows:
        lat = row.get('center_lat')
        lon = row.get('center_lon')
        count = row.get('user_count', 0)
        if lat is None or lon is None or count <= 0:
            continue

        lat_f, lon_f = float(lat), float(lon)
        if not _in_bounds(lat_f, lon_f, bounds):
            continue

        state_name = (row.get('state') or 'State').strip().upper()
        country_code = (row.get('country_code') or '').strip().upper()
        keys = {'state': state_name}
        if country_code:
            keys['country_code'] = country_code

        markers.append({
            'lat': lat_f,
            'lon': lon_f,
            'color': get_marker_color(count),
            'scale': get_marker_scale(count),
            'title': f"{state_name} ({count} users)",
            'user_count': count,
            'keys': keys
        })
    markers.sort(key=lambda m: m['user_count'], reverse=True)
    return markers[:MAX_RENDER_MARKERS]


def _city_grid_markers(bounds=None, cell_size=0.8, tag='Metro', focus_tier='city'):
    """Aggregates map_city_summary rows into spatial grid buckets."""
    effective_bounds = bounds or DEFAULT_ZOOM_BOUNDS
    fetch_cols = ('country_code', 'state', 'city', 'center_lat', 'center_lon', 'user_count')

    try:
        rows = list(app_tables.map_city_summary.search(q.fetch_only(*fetch_cols)))
    except Exception:
        rows = []

    grid_buckets = {}
    for row in rows:
        lat = row.get('center_lat')
        lon = row.get('center_lon')
        count = int(row.get('user_count') or 0)
        if lat is None or lon is None or count <= 0:
            continue

        state_val = (row.get('state') or '').strip().upper()
        coords = _sanitize_coords(lat, lon, state=state_val)
        if not coords:
            continue

        lat_f, lon_f = coords
        if not _in_bounds(lat_f, lon_f, effective_bounds):
            continue

        lat_idx = math.floor(lat_f / cell_size)
        lon_idx = math.floor(lon_f / cell_size)
        bucket_key = (lat_idx, lon_idx)

        if bucket_key not in grid_buckets:
            grid_buckets[bucket_key] = {
                'weighted_lat': 0.0,
                'weighted_lon': 0.0,
                'user_count': 0,
                'cities': set(),
                'states': set(),
                'country_codes': set(),
            }

        b = grid_buckets[bucket_key]
        b['weighted_lat'] += lat_f * count
        b['weighted_lon'] += lon_f * count
        b['user_count'] += count

        city_val = (row.get('city') or '').strip()
        cc_val = (row.get('country_code') or '').strip().upper()
        if city_val:
            b['cities'].add(city_val)
        if state_val:
            b['states'].add(state_val)
        if cc_val:
            b['country_codes'].add(cc_val)

    markers = []
    for b in grid_buckets.values():
        count = b['user_count']
        if count <= 0:
            continue

        center_lat = b['weighted_lat'] / count
        center_lon = b['weighted_lon'] / count

        if len(b['cities']) == 1:
            place_label = next(iter(b['cities'])).title()
        elif len(b['states']) == 1:
            place_label = f"{next(iter(b['states']))} ({len(b['cities'])} cities)"
        elif len(b['country_codes']) == 1:
            place_label = next(iter(b['country_codes']))
        else:
            place_label = "Region"

        cluster_keys = {}
        if len(b['country_codes']) == 1:
            cluster_keys['country_code'] = next(iter(b['country_codes']))
        if len(b['states']) == 1:
            cluster_keys['state'] = next(iter(b['states']))
        if len(b['cities']) == 1:
            cluster_keys['city'] = next(iter(b['cities']))

        is_user_list_level = bool(cluster_keys.get('city') or cluster_keys.get('postal_code'))
        dot_color = USER_LIST_CLUSTER_COLOR if is_user_list_level else get_marker_color(count)

        markers.append({
            'lat': center_lat,
            'lon': center_lon,
            'color': dot_color,
            'scale': get_marker_scale(count),
            'title': f"{place_label} ({count} users) [{tag}]",
            'user_count': count,
            'keys': cluster_keys
        })

    markers.sort(key=lambda m: m['user_count'], reverse=True)
    return markers[:MAX_RENDER_MARKERS]


def _postal_level_markers(bounds=None, tag='Postal'):
    """Returns postal-level cluster markers from map_postal_summary inside viewport bounds."""
    effective_bounds = bounds or DEFAULT_ZOOM_BOUNDS
    fetch_cols = ('country_code', 'postal_code', 'center_lat', 'center_lon', 'user_count')

    try:
        rows = list(app_tables.map_postal_summary.search(q.fetch_only(*fetch_cols)))
    except Exception:
        rows = []

    markers = []
    for row in rows:
        lat = row.get('center_lat')
        lon = row.get('center_lon')
        count = int(row.get('user_count') or 0)
        postal_code = (row.get('postal_code') or '').strip()
        if lat is None or lon is None or count <= 0 or not postal_code:
            continue

        lat_f, lon_f = float(lat), float(lon)
        if not _in_bounds(lat_f, lon_f, effective_bounds):
            continue

        country_code = (row.get('country_code') or '').strip().upper()
        keys = {'postal_code': postal_code}
        if country_code:
            keys['country_code'] = country_code

        markers.append({
            'lat': lat_f,
            'lon': lon_f,
            'color': USER_LIST_CLUSTER_COLOR,
            'scale': get_marker_scale(count),
            'title': f"Postal {postal_code.upper()} ({count} users) [{tag}]",
            'user_count': count,
            'keys': keys
        })

    markers.sort(key=lambda m: m['user_count'], reverse=True)
    return markers[:MAX_RENDER_MARKERS]


def _build_progressive_markers(bounds=None, zoom_level=None, focus_tier=None):
    """Builds progressive markers across zoom levels from pre-aggregated summary tables."""
    spec = _zoom_tier_spec(zoom_level, focus_tier=focus_tier)
    mode = spec['mode']
    cell_size = spec['cell']
    tag = spec['tag']

    if mode == 'state':
        return _state_level_markers(bounds=bounds)

    if mode == 'postal':
        return _postal_level_markers(bounds=bounds, tag=tag)

    return _city_grid_markers(
        bounds=bounds,
        cell_size=cell_size,
        tag=tag,
        focus_tier=focus_tier
    )


@anvil.server.callable
def get_clustered_map_markers(
    cluster_type='region',
    distance_value=None,
    distance_unit='miles',
    active_record_id=None,
    use_test_table=False,
    bounds=None,
    zoom_level=None
):
    cluster_type = (cluster_type or 'region').strip().lower()

    if cluster_type in ['city', 'postal code', 'postal']:
        focus = 'postal' if cluster_type in ['postal code', 'postal'] else 'city'
        return _build_progressive_markers(
            bounds=bounds,
            zoom_level=zoom_level,
            focus_tier=focus
        )

    if cluster_type in ['country', 'state', 'region']:
        if cluster_type == 'region':
            table = app_tables.map_region_summary
            fetch_cols = ('region', 'center_lat', 'center_lon', 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'user_count')
            label_key = 'region'
        elif cluster_type == 'country':
            table = app_tables.map_country_summary
            fetch_cols = ('country_code', 'center_lat', 'center_lon', 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'user_count')
            label_key = 'country_code'
        else:
            table = app_tables.map_state_summary
            fetch_cols = ('country_code', 'state', 'center_lat', 'center_lon', 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'user_count')
            label_key = 'state'

        try:
            all_summary = list(table.search(q.fetch_only(*fetch_cols)))
        except Exception:
            all_summary = []

        markers = []
        for row in all_summary:
            lat = row.get('center_lat')
            lon = row.get('center_lon')
            count = row.get('user_count', 0)
            if lat is None or lon is None or count <= 0:
                continue

            lat_f, lon_f = float(lat), float(lon)
            if not _in_bounds(lat_f, lon_f, bounds):
                continue

            name = row.get(label_key) or 'Cluster'
            markers.append({
                'lat': lat_f,
                'lon': lon_f,
                'color': get_marker_color(count),
                'scale': get_marker_scale(count),
                'title': f"{str(name).title()} ({count} users)",
                'user_count': count,
                'keys': {
                    k: row[k] for k in fetch_cols
                    if k in row and k not in ['center_lat', 'center_lon', 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'user_count']
                }
            })
        markers.sort(key=lambda m: m['user_count'], reverse=True)
        return markers[:MAX_RENDER_MARKERS]

    elif cluster_type in ['miles', 'kilometers', 'mi', 'km']:
        if distance_value is None or str(distance_value).strip() == '':
            return []
        try:
            radius = float(distance_value)
        except (TypeError, ValueError):
            return []
        if radius <= 0:
            return []

        win_width = _viewport_width_in_unit(bounds, cluster_type)
        if win_width is None or win_width > (2.0 * radius):
            return []

        radius_km = radius * 1.60934 if cluster_type in ['miles', 'mi'] else radius

        postal_cols = ('country_code', 'postal_code', 'center_lat', 'center_lon', 'min_lat', 'max_lat', 'min_lon', 'max_lon', 'user_count')
        try:
            postal_rows = list(app_tables.map_postal_summary.search(q.fetch_only(*postal_cols)))
        except Exception:
            postal_rows = []

        in_view_postals = []
        for prow in postal_rows:
            plat = prow.get('center_lat')
            plon = prow.get('center_lon')
            pcode = (prow.get('postal_code') or '').strip()
            pcount = int(prow.get('user_count') or 0)
            if plat is None or plon is None or not pcode or pcount <= 0:
                continue
            plat_f, plon_f = float(plat), float(plon)
            if _in_bounds(plat_f, plon_f, bounds):
                in_view_postals.append({
                    'country_code': (prow.get('country_code') or '').strip().upper(),
                    'postal_code': pcode,
                    'lat': plat_f,
                    'lon': plon_f,
                    'raw_row': prow,
                })

        clusters = []
        for p in in_view_postals:
            lat, lon = p['lat'], p['lon']
            added_to_cluster = False
            for cluster in clusters:
                if calculate_haversine_distance_km(cluster['lat'], cluster['lon'], lat, lon) <= radius_km:
                    cluster['postal_items'].append(p)
                    cluster['lats'].append(lat)
                    cluster['lons'].append(lon)
                    cluster['lat'] = (min(cluster['lats']) + max(cluster['lats'])) / 2.0
                    cluster['lon'] = (min(cluster['lons']) + max(cluster['lons'])) / 2.0
                    added_to_cluster = True
                    break
            if not added_to_cluster:
                clusters.append({
                    'lat': lat,
                    'lon': lon,
                    'lats': [lat],
                    'lons': [lon],
                    'postal_items': [p],
                })

        markers = []
        unit_label = 'miles' if cluster_type in ['miles', 'mi'] else 'km'
        for i, cluster in enumerate(clusters, 1):
            c_lat, c_lon = cluster['lat'], cluster['lon']
            matching_pairs = set()
            for prow in postal_rows:
                pcode = (prow.get('postal_code') or '').strip()
                if not pcode:
                    continue
                if _bbox_overlaps_point_radius(prow, c_lat, c_lon, radius_km):
                    matching_pairs.add(((prow.get('country_code') or '').strip().upper(), pcode))

            user_set = _users_for_postal_pairs(matching_pairs)
            user_list = sorted(list(user_set))
            count = len(user_list)
            markers.append({
                'lat': c_lat,
                'lon': c_lon,
                'color': USER_LIST_CLUSTER_COLOR,
                'scale': get_marker_scale(count),
                'title': f"Cluster {i} ({count} users within {radius:g} {unit_label})",
                'users': user_list
            })

        markers.sort(key=lambda m: len(m['users']), reverse=True)
        return markers[:MAX_RENDER_MARKERS]

    else:
        return []


@anvil.server.callable
def save_map_item(item_id, item_data, use_test_table=True):
    auth_user = get_authenticated_user_row()
    if auth_user is None:
        raise anvil.server.PermissionDenied("You must be logged in to save a map item.")

    user_name = (auth_user['user_name'] or '').strip()
    if not user_name:
        raise ValueError("Authenticated user account is missing a valid user_name.")

    table = get_target_table(use_test_table)
    item_data = dict(item_data or {})
    item_data['user'] = user_name

    country = (item_data.get('country_code') or '').strip().upper()
    state = (item_data.get('state') or '').strip().upper()
    city = (item_data.get('city') or '').strip()
    postal_code = (item_data.get('postal_code') or '').strip()
    address_1 = item_data.get('address_1')
    address_2 = item_data.get('address_2')

    region = item_data.get('region') or get_region_from_country_code(country)
    item_data['region'] = region

    query_parts = [address_1, address_2, city, state, country, postal_code]
    query_string = ", ".join([str(p) for p in query_parts if p])

    lat = item_data.get('latitude')
    lon = item_data.get('longitude')
    formatted_address = item_data.get('formatted_address', '')

    try:
        if query_string.strip() and (lat is None or lon is None):
            location = geolocator.geocode(query_string)
            if location:
                lat = location.latitude
                lon = location.longitude
                formatted_address = location.address
                item_data['latitude'] = lat
                item_data['longitude'] = lon
                item_data['formatted_address'] = formatted_address
    except Exception:
        pass

    now_utc = datetime.datetime.now(datetime.timezone.utc)
    if 'date_time' not in item_data or not item_data['date_time']:
        item_data['date_time'] = now_utc

    existing_row = None
    if item_id is not None and str(item_id).strip() != '':
        try:
            numeric_id = int(item_id)
            existing_row = table.get(id=numeric_id)
        except (ValueError, TypeError):
            existing_row = None

    if existing_row is not None:
        generated_id = int(existing_row['id'])
        item_data['id'] = generated_id
        existing_row.update(**item_data)
    else:
        generated_id = generate_coded_datetime_id(now_utc)
        while table.get(id=generated_id) is not None:
            generated_id += 1
        item_data['id'] = generated_id
        table.add_row(**item_data)

    if lat is not None and lon is not None:
        try:
            lat_f, lon_f = float(lat), float(lon)
            update_summary_tier(app_tables.map_region_summary, {'region': region}, lat_f, lon_f, user_name, table, region=region)
            update_summary_tier(app_tables.map_country_summary, {'country_code': country}, lat_f, lon_f, user_name, table, country_code=country)
            update_summary_tier(app_tables.map_state_summary, {'country_code': country, 'state': state}, lat_f, lon_f, user_name, table, country_code=country, state=state)
            update_summary_tier(app_tables.map_city_summary, {'country_code': country, 'state': state, 'city': city}, lat_f, lon_f, user_name, table, country_code=country, state=state, city=city)
            update_summary_tier(app_tables.map_postal_summary, {'country_code': country, 'postal_code': postal_code}, lat_f, lon_f, user_name, table, country_code=country, postal_code=postal_code)
        except Exception:
            pass

    lookup_table = app_tables.map_user_lookup
    existing_lookup = lookup_table.get(id=generated_id)
    lookup_data = {
        'id': generated_id,
        'user': user_name,
        'region': region,
        'country_code': country,
        'state': state,
        'city': city,
        'postal_code': postal_code
    }

    if existing_lookup:
        existing_lookup.update(**lookup_data)
    else:
        lookup_table.add_row(**lookup_data)

    return generated_id


def update_summary_tier(summary_table, query_dict, lat, lon, user, raw_table, **raw_filters):
    summary_row = summary_table.get(**query_dict)

    bucket_rows = list(raw_table.search(**raw_filters))
    if not bucket_rows:
        if summary_row:
            summary_row.delete()
        return

    lats = []
    lons = []
    users = set()

    for r in bucket_rows:
        r_lat = r.get('latitude')
        r_lon = r.get('longitude')
        r_user = r.get('user')
        r_state = (r.get('state') or '').strip().upper()

        coords = _sanitize_coords(r_lat, r_lon, state=r_state)
        if not coords:
            continue

        rlat_f, rlon_f = coords
        lats.append(rlat_f)
        lons.append(rlon_f)
        if r_user:
            users.add(r_user)

    if not lats or not lons:
        if summary_row:
            summary_row.delete()
        return

    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)

    metrics = {
        'center_lat': (min_lat + max_lat) / 2.0,
        'center_lon': (min_lon + max_lon) / 2.0,
        'min_lat': min_lat,
        'max_lat': max_lat,
        'min_lon': min_lon,
        'max_lon': max_lon,
        'user_count': len(users)
    }

    if summary_row:
        summary_row.update(**metrics)
    else:
        summary_table.add_row(**query_dict, **metrics)


@anvil.server.callable
def get_country_list():
    region_order = ["North America", "South America", "Europe", "Asia", "Africa", "Oceania", "Other"]
    continent_code_mapping = {
        "NA": "North America", "SA": "South America", "EU": "Europe",
        "AS": "Asia", "AF": "Africa", "OC": "Oceania"
    }
    country_list = [("<Select Country>", None)]
    try:
        countries = list(pycountry.countries)
        if countries:
            grouped_countries = {region: [] for region in region_order}
            for c in countries:
                region_name = "Other"
                try:
                    continent_code = country_alpha2_to_continent_code(c.alpha_2)
                    region_name = continent_code_mapping.get(continent_code, "Other")
                except Exception:
                    region_name = "Other"
                grouped_countries[region_name].append((c.name, c.alpha_2))

            for region in region_order:
                sorted_region_countries = sorted(grouped_countries[region], key=lambda x: x[0])
                for name, code in sorted_region_countries:
                    country_list.append((f"[{region}] {name}", code))
    except Exception:
        pass
    return country_list


@anvil.server.callable
def get_states_for_country(country_code):
    state_list = [("<Select State>", None)]
    if not country_code:
        return state_list
    try:
        states = State.get_states_of_country(country_code)
        if states:
            sorted_states = sorted([(s.name, s.iso_code) for s in states], key=lambda x: x[0])
            for state_name, state_code in sorted_states:
                state_list.append((state_name, state_code))
    except Exception:
        pass
    return state_list


@anvil.server.callable
def get_cities_for_state(country_code, state_code):
    city_list = [
        ("<Select City>", None),
        ("If you can't find your city on this list, you can enter it manually at the end of the list.", None),
    ]
    if not country_code or not state_code:
        return city_list
    seen_cities = set()
    try:
        cities = City.get_cities_of_state(country_code, state_code)
        if cities:
            for c_name in sorted([c.name for c in cities]):
                if c_name not in seen_cities:
                    seen_cities.add(c_name)
                    city_list.append((c_name, c_name))
    except Exception:
        pass
    city_list.append(("Enter City Manually", "MANUAL_ENTRY"))
    return city_list

@anvil.server.callable
def geocode_address(address_query):
    parts = [
        address_query.get('address_1'), address_query.get('address_2'),
        address_query.get('city'), address_query.get('state'),
        address_query.get('country'), address_query.get('postal_code')
    ]
    query_string = ", ".join([str(p) for p in parts if p])
    try:
        if query_string.strip():
            location = geolocator.geocode(query_string)
            if location:
                return {
                    'latitude': location.latitude,
                    'longitude': location.longitude,
                    'formatted_address': location.address
                }
    except Exception:
        pass
    return {'latitude': None, 'longitude': None, 'formatted_address': ''}


@anvil.server.callable
def get_users_for_cluster(cluster_keys, page=1, page_size=100, use_test_table=False):
    """
    Restricted to City and Postal Code level clusters only.
    Macro levels (country, state, region) return a guidance notice instead of querying massive row sets.
    """
    if not cluster_keys.get('city') and not cluster_keys.get('postal_code'):
        return {
            'users': [],
            'total_count': 0,
            'page': 1,
            'total_pages': 1,
            'restricted': True
        }

    lookup_table = app_tables.map_user_lookup

    query_filters = {}
    for k, v in cluster_keys.items():
        if k in ['country_code', 'state', 'city', 'postal_code'] and v:
            query_filters[k] = v

    matching_rows = lookup_table.search(q.fetch_only('user'), **query_filters)
    unique_users = sorted(list({row['user'] for row in matching_rows if row.get('user')}))
    total_count = len(unique_users)

    if not unique_users:
        return {
            'users': ['Unknown User'],
            'total_count': 0,
            'page': 1,
            'total_pages': 1,
            'restricted': False
        }

    total_pages = max(1, math.ceil(total_count / page_size))
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size

    paginated_users = unique_users[start_idx:end_idx]

    return {
        'users': paginated_users,
        'total_count': total_count,
        'page': page,
        'total_pages': total_pages,
        'restricted': False
    }