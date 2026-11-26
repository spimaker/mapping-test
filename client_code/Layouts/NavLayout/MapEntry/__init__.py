from ._anvil_designer import MapEntryTemplate
import anvil.server
import anvil.js
from anvil import alert
import math
import re
from ....AuthVisibilityService import auth_visibility


class MapEntry(MapEntryTemplate):

  def __init__(self, **properties):
      self.init_components(**properties)
      self.last_saved_record_id = None
      self._refresh_lock = False
      self._loading_map = False
      self._initial_centered = False
      self._last_viewport_sig = None
      self._debounce_timeout_id = None
      self._debounce_callback = self._run_debounced_refresh
      self._js_gmap = None
      self._radial_prompt_shown = False
      self._last_radial_zoom = None
      self._radius_selected = False
      self._user_postal_marker_data = None

      self.use_test_table = True

      if hasattr(self, "User_Name_Value") and self.User_Name_Value is not None:
        self.User_Name_Value.set_event_handler(
            "focus", self._populate_logged_in_user_name
        )
        try:
          dom_node = anvil.js.get_dom_node(self.User_Name_Value)
          dom_node.addEventListener(
              "click", lambda e: self._populate_logged_in_user_name()
          )
        except Exception:
          pass

      if hasattr(self, "User_Name_Value") and self.User_Name_Value is not None:
            self.User_Name_Value.set_event_handler(
                "focus", self._populate_logged_in_user_name
            )

      if hasattr(self, "Map_my_location") and self.Map_my_location is not None:
        auth_visibility.bind(self.Map_my_location, "map_my_location")
        self.Map_my_location.set_event_handler(
            "click", self.map_my_location_click
        )

      auth_visibility.refresh_auth_state()

      self.Info_Link.role = "input-border"

      self.Threshold_Label.visible = False
      self.Threshold_Dropdown.visible = False

      if hasattr(self, "Fullscreen_button"):
        self.Fullscreen_button.set_event_handler(
            "click", self.full_screen_map_button_click
        )

      try:
        self.Country_Code_Value.items = anvil.server.call("get_country_list")
      except Exception as e:
        print(f"get_country_list error: {e}")

      if hasattr(self, "Cluster_Type_Dropdown"):
        self.Cluster_Type_Dropdown.selected_value = "Country"

      self.refresh_map_display(cluster_type="Country", force=True)

      for evt in ("bounds_changed", "zoom_changed", "dragend", "idle"):
        try:
          self.map_1.set_event_handler(
              evt, lambda e=evt, **kw: self._on_map_viewport_change(evt_name=e, **kw)
          )
        except Exception as ex:
          print(f"Failed attaching {evt}: {ex}")

      self.repeating_panel_1.items = [
          {"range": "1 – 999 records", "role": "swatch-8"},
          {"range": "1,000 – 9,999 records", "role": "swatch-10"},
          {"range": "10,000 – 99,999 records", "role": "swatch-12"},
          {"range": "100,000 – 249,999 records", "role": "swatch-16"},
          {"range": "250,000 – 999,999 records", "role": "swatch-18"},
          {"range": "1,000,000+ records", "role": "swatch-20"},
      ]

  def _populate_logged_in_user_name(self, **event_args):
      if getattr(self, "_checking_user_auth", False):
        return
      now_ts = anvil.js.window.performance.now()
      if (now_ts - getattr(self, "_last_auth_prompt_ts", 0.0)) < 1500.0:
        return

      self._checking_user_auth = True
      try:
        user_name = anvil.server.call("get_authenticated_user_name")
        if user_name:
          self.User_Name_Value.text = user_name
        else:
          try:
            anvil.js.get_dom_node(self.User_Name_Value).blur()
          except Exception:
            pass
          self._last_auth_prompt_ts = anvil.js.window.performance.now()
          alert("You must be logged in to enter a Map Item.")
          self._last_auth_prompt_ts = anvil.js.window.performance.now()
      except Exception as e:
        print(f"Error fetching authenticated user_name: {e}")
      finally:
        self._checking_user_auth = False

        
  @staticmethod
  def _is_radial_mode(cluster_type):
    return bool(
        cluster_type
        and str(cluster_type).strip().lower()
        in ["miles", "kilometers", "mi", "km"]
    )

  @staticmethod
  def _parse_radius_value(distance_value):
    if distance_value is None:
      return None
    if isinstance(distance_value, (int, float)):
      val = float(distance_value)
      return val if val > 0 else None
    match = re.search(r"[-+]?\d*\.?\d+", str(distance_value))
    if not match:
      return None
    val = float(match.group(0))
    return val if val > 0 else None

  @staticmethod
  def _haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    return r * 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

  def _get_viewport_width_in_unit(self, bounds, cluster_type):
    if not bounds:
      return None
    try:
      north = float(bounds["north"])
      south = float(bounds["south"])
      east = float(bounds["east"])
      west = float(bounds["west"])
      mid_lat = (north + south) / 2.0
      width_km = self._haversine_km(mid_lat, west, mid_lat, east)
      unit = str(cluster_type or "").strip().lower()
      if unit in ["miles", "mi"]:
        return width_km / 1.60934
      return width_km
    except Exception:
      return None

  def _find_js_gmap(self):
    if self._js_gmap is not None:
      return self._js_gmap

    for attr_name in ("_map", "map", "_gmap", "gmap"):
      obj = getattr(self.map_1, attr_name, None)
      if obj is not None and (
          hasattr(obj, "getBounds") or hasattr(obj, "getZoom")
      ):
        self._js_gmap = obj
        return self._js_gmap

    try:
      for k, v in getattr(self.map_1, "__dict__", {}).items():
        if v is not None and (
            hasattr(v, "getBounds") or hasattr(v, "getZoom")
        ):
          self._js_gmap = v
          return self._js_gmap
    except Exception:
      pass

    try:
      dom_node = anvil.js.get_dom_node(self.map_1)
      found = anvil.js.call_js(
          """
          (function(root) {
              if (!root) return null;
              var queue = [root];
              var seen = new Set();
              while (queue.length > 0) {
                  var el = queue.shift();
                  if (!el || seen.has(el)) continue;
                  seen.add(el);
                  var keys = Object.getOwnPropertyNames(el);
                  for (var i = 0; i < keys.length; i++) {
                      var val = el[keys[i]];
                      if (val && typeof val === 'object' && typeof val.getBounds === 'function' && typeof val.getZoom === 'function') {
                          return val;
                      }
                  }
                  if (el.children) {
                      for (var c = 0; c < el.children.length; c++) {
                          queue.push(el.children[c]);
                      }
                  }
              }
              return null;
          })
          """,
          dom_node,
      )
      if found is not None:
        self._js_gmap = found
        return self._js_gmap
    except Exception:
      pass

    return None

  def _extract_bounds_from_obj(self, b):
    if not b:
      return None
    try:
      if (
          hasattr(b, "north")
          and hasattr(b, "south")
          and hasattr(b, "east")
          and hasattr(b, "west")
      ):
        return {
            "north": round(float(b.north), 5),
            "south": round(float(b.south), 5),
            "east": round(float(b.east), 5),
            "west": round(float(b.west), 5),
        }
      if hasattr(b, "getNorthEast") and hasattr(b, "getSouthWest"):
        ne = b.getNorthEast()
        sw = b.getSouthWest()
        n_lat = ne.lat() if callable(getattr(ne, "lat", None)) else ne.lat
        e_lng = ne.lng() if callable(getattr(ne, "lng", None)) else ne.lng
        s_lat = sw.lat() if callable(getattr(sw, "lat", None)) else sw.lat
        w_lng = sw.lng() if callable(getattr(sw, "lng", None)) else sw.lng
        return {
            "north": round(float(n_lat), 5),
            "east": round(float(e_lng), 5),
            "south": round(float(s_lat), 5),
            "west": round(float(w_lng), 5),
        }
    except Exception:
      pass
    return None

  def _get_current_center(self):
    try:
      c = getattr(self.map_1, "center", None)
      if c is not None:
        lat = (
            c.lat() if callable(getattr(c, "lat", None)) else getattr(c, "lat", None)
        )
        lng = (
            c.lng() if callable(getattr(c, "lng", None)) else getattr(c, "lng", None)
        )
        if lat is not None and lng is not None:
          return {"lat": round(float(lat), 5), "lon": round(float(lng), 5)}
    except Exception:
      pass

    gmap = self._find_js_gmap()
    if gmap is not None and hasattr(gmap, "getCenter"):
      try:
        c = gmap.getCenter()
        if c is not None:
          lat = (
              c.lat()
              if callable(getattr(c, "lat", None))
              else getattr(c, "lat", None)
          )
          lng = (
              c.lng()
              if callable(getattr(c, "lng", None))
              else getattr(c, "lng", None)
          )
          if lat is not None and lng is not None:
            return {"lat": round(float(lat), 5), "lon": round(float(lng), 5)}
      except Exception:
        pass
    return None

  def _get_current_zoom_and_bounds(self):
    zoom_level = None
    bounds = None

    if hasattr(self.map_1, "zoom"):
      try:
        zoom_level = self.map_1.zoom
      except Exception:
        zoom_level = None

    if hasattr(self.map_1, "get_bounds"):
      try:
        bounds = self._extract_bounds_from_obj(self.map_1.get_bounds())
      except Exception:
        bounds = None

    gmap = self._find_js_gmap()
    if gmap is not None:
      try:
        if zoom_level is None and hasattr(gmap, "getZoom"):
          z_val = gmap.getZoom()
          if callable(z_val):
            z_val = z_val()
          zoom_level = z_val
      except Exception:
        pass
      try:
        if bounds is None and hasattr(gmap, "getBounds"):
          b_val = gmap.getBounds()
          if callable(b_val):
            b_val = b_val()
          bounds = self._extract_bounds_from_obj(b_val)
      except Exception:
        pass

    if bounds is None and zoom_level is not None:
      center = self._get_current_center()
      if center is not None:
        try:
          z_num = max(1.0, float(zoom_level))
          lat_half = 170.0 / (2.0**z_num)
          lon_half = 360.0 / (2.0**z_num)
          bounds = {
              "north": round(min(85.0, center["lat"] + lat_half), 5),
              "south": round(max(-85.0, center["lat"] - lat_half), 5),
              "east": round(min(180.0, center["lon"] + lon_half), 5),
              "west": round(max(-180.0, center["lon"] - lon_half), 5),
          }
        except Exception:
          pass

    return zoom_level, bounds

  def _clear_debounce_timeout(self):
    if self._debounce_timeout_id is not None:
      try:
        anvil.js.window.clearTimeout(self._debounce_timeout_id)
      except Exception:
        pass
      self._debounce_timeout_id = None

  def _on_map_viewport_change(self, evt_name="viewport", **event_args):
    if self._refresh_lock or self._loading_map:
      return
    self._clear_debounce_timeout()
    self._debounce_timeout_id = anvil.js.window.setTimeout(
        self._debounce_callback, 450
    )

  def _run_debounced_refresh(self):
    self._debounce_timeout_id = None
    self._refresh_lock = False
    self._loading_map = False
    self._refresh_current_cluster_mode(force=False)

  def _refresh_current_cluster_mode(self, force=True):
    cluster_val = (
        self.Cluster_Type_Dropdown.selected_value
        if hasattr(self, "Cluster_Type_Dropdown")
        else "Country"
    )
    dist_val = (
        self.Threshold_Dropdown.selected_value
        if hasattr(self, "Threshold_Dropdown")
        else None
    )
    self.refresh_map_display(
        cluster_type=cluster_val, distance_value=dist_val, force=force
    )

  def _on_fullscreen_toggled(self):
    self._last_viewport_sig = None
    self._last_radial_zoom = None
    self._radial_prompt_shown = False
    self._refresh_current_cluster_mode(force=True)

  def _show_paginated_user_alert(self, cluster_title, all_users):
    unique_users = sorted(list({u for u in (all_users or []) if u}))
    total_count = len(unique_users)
    if not unique_users:
      unique_users = ["Unknown User"]

    current_page = 1
    page_size = 100
    total_pages = (
        max(1, math.ceil(total_count / page_size)) if total_count > 0 else 1
    )

    while True:
      current_page = max(1, min(current_page, total_pages))
      start_idx = (current_page - 1) * page_size
      end_idx = start_idx + page_size
      page_users = unique_users[start_idx:end_idx]

      disp_start = (
          ((current_page - 1) * page_size) + 1 if total_count > 0 else 0
      )
      disp_end = min(current_page * page_size, total_count)

      formatted_users = "\n".join([f"• {u}" for u in page_users])
      page_info = f"Page {current_page} of {total_pages} (Showing {disp_start}-{disp_end} of {total_count})"
      content = f"{cluster_title}\n\n{page_info}\n\n{formatted_users}"

      buttons = []
      if current_page > 1:
        buttons.append(("Previous", "prev"))
      if current_page < total_pages:
        buttons.append(("Next", "next"))
      buttons.append(("Close", None))

      action = alert(
          content=content, title="Cluster Users", large=True, buttons=buttons
      )

      if action == "next":
        current_page += 1
      elif action == "prev":
        current_page -= 1
      else:
        break

  def clear_button_click(self, **event_args):
      self.User_Name_Value.text = ""
      self.Country_Code_Value.selected_value = None
      self.State_Province_Region_Value.selected_value = None
      self.City_Value.selected_value = None
      self.City_Value.items = [("<Select City>", None)]

      self.Custom_City_Label.visible = False
      self.Custom_City_TextBox.visible = False
      self.Custom_City_TextBox.text = ""

      self.Postal_Code_Value.text = ""
      self.Address1_Value.text = ""
      self.Address2_Value.text = ""
      self.Latitude_Value.text = ""
      self.Longitude_Value.text = ""
      self.Formatted_Address_Value.text = ""
        
  def search_button_click(self, **event_args):
    try:
      address_query = {
          "address_1": self.Address1_Value.text,
          "address_2": self.Address2_Value.text,
          "city": self.City_Value.selected_value
          or self.Custom_City_TextBox.text,
          "state": self.State_Province_Region_Value.selected_value,
          "country": self.Country_Code_Value.selected_value,
          "postal_code": self.Postal_Code_Value.text,
      }
      result = anvil.server.call("geocode_address", address_query)
      if result:
        self.Latitude_Value.text = str(result.get("latitude", ""))
        self.Longitude_Value.text = str(result.get("longitude", ""))
        self.Formatted_Address_Value.text = result.get("formatted_address", "")
    except Exception as e:
      print(f"Error during search: {e}")

  def full_screen_map_button_click(self, **event_args):
    try:
      dom_node = anvil.js.get_dom_node(self.map_1)
      on_toggle = self._on_fullscreen_toggled
      anvil.js.call_js(
          """
          (function(root, notifyToggle) {
              if (!root) return;

              var EXIT_BTN_ID = 'anvil-exit-map-fullscreen-btn';
              var STYLE_ID = 'anvil-fullscreen-modal-zindex-style';

              function raiseModalsAboveFullscreen() {
                  if (!document.getElementById(STYLE_ID)) {
                      var style = document.createElement('style');
                      style.id = STYLE_ID;
                      style.textContent = [
                          '.modal-backdrop { z-index: 199990 !important; }',
                          '.modal, [role="dialog"], .anvil-alert { z-index: 200000 !important; }'
                      ].join('\\n');
                      document.head.appendChild(style);
                  }
                  var nodes = document.querySelectorAll('.modal, .modal-backdrop, [role="dialog"], .anvil-alert');
                  for (var i = 0; i < nodes.length; i++) {
                      nodes[i].style.zIndex = nodes[i].classList.contains('modal-backdrop') ? '199990' : '200000';
                  }
              }

              function startModalWatcher() {
                  raiseModalsAboveFullscreen();
                  if (window._anvilFsModalObserver) {
                      window._anvilFsModalObserver.disconnect();
                  }
                  var obs = new MutationObserver(function() {
                      raiseModalsAboveFullscreen();
                  });
                  obs.observe(document.body, { childList: true, subtree: true });
                  window._anvilFsModalObserver = obs;
              }

              function stopModalWatcher() {
                  if (window._anvilFsModalObserver) {
                      window._anvilFsModalObserver.disconnect();
                      window._anvilFsModalObserver = null;
                  }
                  var style = document.getElementById(STYLE_ID);
                  if (style && style.parentNode) {
                      style.parentNode.removeChild(style);
                  }
              }

              function removeExitButton() {
                  var existing = document.getElementById(EXIT_BTN_ID);
                  if (existing && existing.parentNode) {
                      existing.parentNode.removeChild(existing);
                  }
              }

              function triggerMapResize(el) {
                  if (window.google && window.google.maps && window.google.maps.event) {
                      var mapDiv = el.querySelector('.gm-style') || el;
                      if (mapDiv && mapDiv.__gm && mapDiv.__gm.gm) {
                          window.google.maps.event.trigger(mapDiv.__gm.gm, 'resize');
                      }
                  }
              }

              function collapseMap(el) {
                  el.dataset.anvilMapExpanded = 'false';
                  el.setAttribute('style', el.dataset.prevStyle || '');
                  removeExitButton();
                  stopModalWatcher();
                  triggerMapResize(el);
                  setTimeout(function() {
                      if (typeof notifyToggle === 'function') notifyToggle();
                  }, 150);
              }

              function createExitButton(el) {
                  removeExitButton();
                  var btn = document.createElement('button');
                  btn.id = EXIT_BTN_ID;
                  btn.type = 'button';
                  btn.textContent = 'Exit Full Screen';
                  btn.style.position = 'fixed';
                  btn.style.top = '16px';
                  btn.style.right = '16px';
                  btn.style.zIndex = '100000';
                  btn.style.padding = '10px 16px';
                  btn.style.fontSize = '14px';
                  btn.style.fontWeight = '600';
                  btn.style.color = '#ffffff';
                  btn.style.backgroundColor = '#1a73e8';
                  btn.style.border = 'none';
                  btn.style.borderRadius = '6px';
                  btn.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.35)';
                  btn.style.cursor = 'pointer';
                  btn.addEventListener('click', function(ev) {
                      ev.preventDefault();
                      ev.stopPropagation();
                      collapseMap(el);
                  });
                  document.body.appendChild(btn);
              }

              function toggleExpanded(el) {
                  var isExpanded = el.dataset.anvilMapExpanded === 'true';
                  if (!isExpanded) {
                      el.dataset.prevStyle = el.getAttribute('style') || '';
                      el.dataset.anvilMapExpanded = 'true';
                      el.style.position = 'fixed';
                      el.style.top = '0';
                      el.style.left = '0';
                      el.style.width = '100vw';
                      el.style.height = '100vh';
                      el.style.zIndex = '99999';
                      el.style.background = '#ffffff';
                      createExitButton(el);
                      startModalWatcher();
                      triggerMapResize(el);
                  } else {
                      collapseMap(el);
                  }
                  setTimeout(function() {
                      if (typeof notifyToggle === 'function') notifyToggle();
                  }, 150);
              }

              if (document && document.fullscreenEnabled) {
                  var queue = [root];
                  var visited = new Set();
                  while (queue.length > 0) {
                      var node = queue.shift();
                      if (!node || visited.has(node)) continue;
                      visited.add(node);
                      if (node.tagName === 'BUTTON') {
                          var label = (node.getAttribute('aria-label') || node.title || '').toLowerCase();
                          if (label.indexOf('fullscreen') !== -1 || label.indexOf('full screen') !== -1) {
                              node.click();
                              startModalWatcher();
                              setTimeout(function() {
                                  if (typeof notifyToggle === 'function') notifyToggle();
                              }, 150);
                              return;
                          }
                      }
                      if (node.shadowRoot) queue.push(node.shadowRoot);
                      if (node.children) {
                          for (var i = 0; i < node.children.length; i++) {
                              queue.push(node.children[i]);
                          }
                      }
                  }
              }

              toggleExpanded(root);
          })
          """,
          dom_node,
          on_toggle,
      )
    except Exception as e:
      alert(f"Error toggling fullscreen map: {e}", title="Fullscreen Error")

  def country_dropdown_change(self, **event_args):
    selected_country = self.Country_Code_Value.selected_value
    self.State_Province_Region_Value.items = []
    self.State_Province_Region_Value.selected_value = None
    self.City_Value.items = []
    self.City_Value.selected_value = None

    if selected_country:
      try:
        self.State_Province_Region_Value.items = anvil.server.call(
            "get_states_for_country", selected_country
        )
      except Exception as e:
        print(f"Error loading states: {e}")

  def state_dropdown_change(self, **event_args):
    selected_country = self.Country_Code_Value.selected_value
    selected_state = self.State_Province_Region_Value.selected_value
    self.City_Value.items = [("<Select City>", None)]
    self.City_Value.selected_value = None

    if selected_country and selected_state:
      try:
        self.City_Value.items = anvil.server.call(
            "get_cities_for_state", selected_country, selected_state
        )
      except Exception as e:
        print(f"Error loading cities: {e}")

  def city_dropdown_change(self, **event_args):
    selected_city = self.City_Value.selected_value
    if selected_city == "MANUAL_ENTRY":
      self.Custom_City_Label.visible = True
      self.Custom_City_TextBox.visible = True
      self.Custom_City_TextBox.focus()
    else:
      self.Custom_City_Label.visible = False
      self.Custom_City_TextBox.visible = False
      self.Custom_City_TextBox.text = ""

  def refresh_map_display(
      self,
      cluster_type=None,
      distance_value=None,
      active_record_id=None,
      force=False,
  ):
    self._clear_debounce_timeout()
    if self._refresh_lock:
      return
    self._refresh_lock = True
    self._loading_map = True
    try:
      cluster_type = cluster_type or "region"
      zoom_level, bounds = self._get_current_zoom_and_bounds()

      is_radial = self._is_radial_mode(cluster_type)
      if is_radial:
        radius = self._parse_radius_value(distance_value)
        if radius is None:
          return

        target_width = 2.0 * radius
        win_width = self._get_viewport_width_in_unit(bounds, cluster_type)

        if win_width is None or win_width > target_width:
          self.map_1.clear()
          self._render_user_postal_marker()
          zoom_changed = zoom_level != self._last_radial_zoom
          if not self._radial_prompt_shown or zoom_changed:
            self._radial_prompt_shown = True
            self._last_radial_zoom = zoom_level
            alert(
                content=(
                    "Center the map on your area of interest and zoom in"
                    " closer."
                ),
                title="Zoom In to View Radius Clusters",
                large=False,
            )
          return

        self._radial_prompt_shown = False
        self._last_radial_zoom = zoom_level

      viewport_sig = (
          str(cluster_type).lower(),
          str(distance_value),
          str(zoom_level),
          str(bounds),
      )
      if not force and viewport_sig == self._last_viewport_sig:
        return
      self._last_viewport_sig = viewport_sig

      markers = anvil.server.call(
          "get_clustered_map_markers",
          cluster_type=cluster_type,
          distance_value=radius if is_radial else distance_value,
          active_record_id=active_record_id,
          use_test_table=self.use_test_table,
          bounds=bounds,
          zoom_level=zoom_level,
      )

      self.map_1.clear()

      for m in markers[:400]:
        lat_lng = self.map_1.LatLng(m["lat"], m["lon"])
        title = m.get("title", "Cluster")
        cluster_keys = m.get("keys", {})
        cluster_users = m.get("users")
        has_user_popup = (cluster_users is not None) or bool(
            cluster_keys.get("city") or cluster_keys.get("postal_code")
        )
        hex_color = (
            "#9370DB"
            if (is_radial or has_user_popup)
            else m.get("color", "#ADD8E6")
        )

        marker_symbol = self.map_1.Symbol(
            path=self.map_1.SymbolPath.CIRCLE,
            scale=m.get("scale", 12),
            fill_color=hex_color,
            fill_opacity=0.9,
            stroke_color="#FFFFFF",
            stroke_weight=2,
        )

        marker = self.map_1.Marker(
            position=lat_lng,
            title=title,
            icon=marker_symbol,
            animation=self.map_1.Animation.DROP,
        )

        def make_click_handler(cluster_title, keys, radial_users):
          def marker_click_handler(sender, **event_args):
            if radial_users is not None:
              self._show_paginated_user_alert(cluster_title, radial_users)
              return

            if not keys.get("city") and not keys.get("postal_code"):
              alert(
                  content=(
                      f"{cluster_title}\n\nRegional, country, and state clusters"
                      " contain too many records to list individually.\n\nPlease"
                      " zoom in to the City or Postal Code level to view user"
                      " lists."
                  ),
                  title="Cluster Overview",
                  large=False,
              )
              return

            current_page = 1
            page_size = 100

            while True:
              response = anvil.server.call(
                  "get_users_for_cluster",
                  cluster_keys=keys,
                  page=current_page,
                  page_size=page_size,
                  use_test_table=self.use_test_table,
              )

              if response.get("restricted"):
                alert(
                    content=(
                        "Please zoom in to the City or Postal Code level to view"
                        " user lists."
                    ),
                    title="Cluster Overview",
                )
                break

              users = response.get("users", ["Unknown User"])
              total_count = response.get("total_count", 0)
              current_page = response.get("page", 1)
              total_pages = response.get("total_pages", 1)

              start_idx = (
                  ((current_page - 1) * page_size) + 1 if total_count > 0 else 0
              )
              end_idx = min(current_page * page_size, total_count)

              formatted_users = "\n".join([f"• {u}" for u in users])
              page_info = f"Page {current_page} of {total_pages} (Showing {start_idx}-{end_idx} of {total_count})"

              content = f"{cluster_title}\n\n{page_info}\n\n{formatted_users}"

              buttons = []
              if current_page > 1:
                buttons.append(("Previous", "prev"))
              if current_page < total_pages:
                buttons.append(("Next", "next"))
              buttons.append(("Close", None))

              action = alert(
                  content=content,
                  title="Cluster Users",
                  large=True,
                  buttons=buttons,
              )

              if action == "next":
                current_page += 1
              elif action == "prev":
                current_page -= 1
              else:
                break

          return marker_click_handler

        marker.set_event_handler(
            "click", make_click_handler(title, cluster_keys, cluster_users)
        )
        self.map_1.add_component(marker)

      self._render_user_postal_marker()

      if markers and not self._initial_centered:
        latest = markers[0]
        self.map_1.center = self.map_1.LatLng(latest["lat"], latest["lon"])
        self.map_1.zoom = 4
        self._initial_centered = True
    finally:
      self._refresh_lock = False
      self._loading_map = False

  def cluster_dropdown_change(self, sender, **event_args):
    val = sender.selected_value
    is_radial = self._is_radial_mode(val)
    self._radial_prompt_shown = False
    self._last_radial_zoom = None
    self._radius_selected = False

    self.Threshold_Label.visible = is_radial
    self.Threshold_Dropdown.visible = is_radial

    if is_radial:
      self.Threshold_Dropdown.selected_value = None
      self.Threshold_Dropdown.focus()
      return

    self.refresh_map_display(cluster_type=val, distance_value=None, force=True)

  def threshold_dropdown_change(self, sender, **event_args):
    self._radial_prompt_shown = False
    self._last_radial_zoom = None
    self._radius_selected = (
        self._parse_radius_value(sender.selected_value) is not None
    )
    cluster_type_val = self.Cluster_Type_Dropdown.selected_value
    self.refresh_map_display(
        cluster_type=cluster_type_val,
        distance_value=sender.selected_value,
        force=True,
    )

  def Info_Link_click(self, **event_args):
    alert(
        content=(
            "Clusters allow you to zoom in from Global Region down to Postal"
            " Code or select Miles/Kilometers and a radius to view the records"
            " at these levels.\nAs you zoom farther into the map, an increasing"
            " number of map markers will appear. When a marker reaches its most"
            " granular level, it will change colors from blue to purple and when"
            " clicked will display users covered by that marker."
        ),
        title="Cluster Information",
        large=False,
    )

  def Build_map_user_lookup_click(self, **event_args):
    """Triggered when the backfill button is clicked to launch the background task."""
    try:
      use_test = getattr(self, "use_test_table", True)
      result_message = anvil.server.call(
          "populate_map_user_lookup", use_test_table=use_test
      )
      alert(
          content=result_message, title="Background Task Started", large=False
      )
    except Exception as e:
      alert(
          content=f"Error launching background task: {e}",
          title="Error",
          large=False,
      )

  def _render_user_postal_marker(self):
    if not self._user_postal_marker_data:
      return
    if not auth_visibility.is_feature_enabled("map_my_location"):
      self._user_postal_marker_data = None
      return

    data = self._user_postal_marker_data
    lat_lng = self.map_1.LatLng(data["lat"], data["lon"])
    postal_label = data.get("postal_code") or "My Postal Code"

    green_symbol = self.map_1.Symbol(
        path=self.map_1.SymbolPath.CIRCLE,
        scale=14,
        fill_color="#2E7D32",
        fill_opacity=1.0,
        stroke_color="#FFFFFF",
        stroke_weight=2.5,
    )

    marker = self.map_1.Marker(
        position=lat_lng,
        title=f"My Location ({postal_label})",
        icon=green_symbol,
        z_index=9999,
    )
    self.map_1.add_component(marker)

  def map_my_location_click(self, **event_args):
    if not auth_visibility.is_feature_enabled("map_my_location"):
      return

    try:
      loc = anvil.server.call(
          "get_logged_in_user_postal_location",
          use_test_table=self.use_test_table,
      )
      if not loc:
        alert("No postal code coordinates were found for your account.")
        return

      self._user_postal_marker_data = loc
      target_pos = self.map_1.LatLng(loc["lat"], loc["lon"])

      # Center and zoom into the user's postal code area
      self.map_1.center = target_pos
      self.map_1.zoom = 12

      # Reset signature so clusters refresh for the new viewport and re-draw the green marker
      self._last_viewport_sig = None
      self._refresh_current_cluster_mode(force=True)
    except Exception as e:
      alert(f"Could not locate your postal code: {e}")

  def save_button_click(self, **event_args):
      try:
        logged_in_email = anvil.server.call("get_authenticated_user")
        if not logged_in_email:
          alert("Please log in before saving a map item.")
          return

        selected_city = self.City_Value.selected_value
        final_city = (
            self.Custom_City_TextBox.text
            if selected_city == "MANUAL_ENTRY"
            else selected_city
        )

        record_data = {
            "country_code": self.Country_Code_Value.selected_value,
            "state": self.State_Province_Region_Value.selected_value,
            "city": final_city,
            "postal_code": self.Postal_Code_Value.text,
            "address_1": self.Address1_Value.text,
            "address_2": self.Address2_Value.text,
            "latitude": (
                float(self.Latitude_Value.text)
                if self.Latitude_Value.text
                else None
            ),
            "longitude": (
                float(self.Longitude_Value.text)
                if self.Longitude_Value.text
                else None
            ),
            "formatted_address": self.Formatted_Address_Value.text,
        }

        saved_id = anvil.server.call(
            "save_map_item",
            None,
            record_data,
            use_test_table=self.use_test_table,
        )
        if saved_id:
          table_label = "MapItems_Test" if self.use_test_table else "MapItems"
          alert(f"Record saved successfully to {table_label} (ID: {saved_id})!")
          self.refresh_map_display(active_record_id=saved_id, force=True)
      except Exception as e:
        alert(f"Error saving record: {e}")