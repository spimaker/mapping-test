import anvil.server
import anvil.tables as tables
from anvil.tables import app_tables

@anvil.server.callable
def seed_test_data():
  csv_data = """id,user_name,address_1,address_2,city,state,postal_code,country_code,latitude,longitude,formatted_address
ID001,User 1,350 5th Ave,Suite 1200,New York,NY,10118,US,40.7484,-73.9857,350 5th Ave, New York, NY 10118
ID002,User 2,405 Lexington Ave,Floor 15,New York,NY,10174,US,40.7516,-73.9755,405 Lexington Ave, New York, NY 10174
ID003,User 3,20 W 34th St,,New York,NY,10001,US,40.7498,-73.9855,20 W 34th St, New York, NY 10001
ID004,User 4,11 W 42nd St,Apt 4B,New York,NY,10036,US,40.7554,-73.9845,11 W 42nd St, New York, NY 10036
ID005,User 5,750 7th Ave,,New York,NY,10019,US,40.7617,-73.9830,750 7th Ave, New York, NY 10019
ID006,User 6,1221 Avenue of the Americas,,New York,NY,10020,US,40.7590,-73.9822,1221 Avenue of the Americas, New York, NY 10020
ID007,User 7,1515 Broadway,,New York,NY,10036,US,40.7580,-73.9855,1515 Broadway, New York, NY 10036
ID008,User 8,200 Park Ave,,New York,NY,10166,US,40.7533,-73.9757,200 Park Ave, New York, NY 10166
ID009,User 9,601 Lexington Ave,,New York,NY,10022,US,40.7588,-73.9682,601 Lexington Ave, New York, NY 10022
ID010,User 10,485 Lexington Ave,,New York,NY,10017,US,40.7538,-73.9734,485 Lexington Ave, New York, NY 10017
ID011,User 11,230 Park Ave,,New York,NY,10169,US,40.7539,-73.9760,230 Park Ave, New York, NY 10169
ID012,User 12,500 5th Ave,,New York,NY,10110,US,40.7538,-73.9830,500 5th Ave, New York, NY 10110
ID013,User 13,109 E 42nd St,,New York,NY,10017,US,40.7525,-73.9772,109 E 42nd St, New York, NY 10017
ID014,User 14,30 Rockefeller Plaza,,New York,NY,10112,US,40.7587,-73.9787,30 Rockefeller Plaza, New York, NY 10112
ID015,User 15,1250 Broadway,,New York,NY,10001,US,40.7483,-73.9873,1250 Broadway, New York, NY 10001
ID016,User 16,1440 Broadway,,New York,NY,10018,US,40.7534,-73.9860,1440 Broadway, New York, NY 10018
ID017,User 17,55 Broadway,,New York,NY,10006,US,40.7061,-74.0135,55 Broadway, New York, NY 10006
ID018,User 18,1 Wall St,,New York,NY,10005,US,40.7071,-74.0118,1 Wall St, New York, NY 10005
ID019,User 19,70 Pine St,,New York,NY,10005,US,40.7066,-74.0084,70 Pine St, New York, NY 10005
ID020,User 20,120 Broadway,,New York,NY,10271,US,40.7081,-74.0112,120 Broadway, New York, NY 10271
ID021,User 21,80 Pine St,,New York,NY,10005,US,40.7062,-74.0076,80 Pine St, New York, NY 10005
ID022,User 22,14 Wall St,,New York,NY,10005,US,40.7075,-74.0113,14 Wall St, New York, NY 10005
ID023,User 23,222 Broadway,,New York,NY,10038,US,40.7112,-74.0070,222 Broadway, New York, NY 10038
ID024,User 24,150 Broadway,,New York,NY,10038,US,40.7093,-74.0101,150 Broadway, New York, NY 10038
ID025,User 25,175 Broadway,,New York,NY,10038,US,40.7118,-74.0080,175 Broadway, New York, NY 10038
ID026,User 26,633 W 5th St,Suite 2800,Los Angeles,CA,90071,US,34.0515,-118.2543,633 W 5th St, Los Angeles, CA 90071
ID027,User 27,350 S Grand Ave,,Los Angeles,CA,90071,US,34.0512,-118.2517,350 S Grand Ave, Los Angeles, CA 90071
ID028,User 28,400 S Hope St,,Los Angeles,CA,90071,US,34.0522,-118.2548,400 S Hope St, Los Angeles, CA 90071
ID029,User 29,444 S Flower St,,Los Angeles,CA,90071,US,34.0531,-118.2555,444 S Flower St, Los Angeles, CA 90071
ID030,User 30,555 S Flower St,,Los Angeles,CA,90071,US,34.0503,-118.2559,555 S Flower St, Los Angeles, CA 90071
ID031,User 31,777 S Figueroa St,,Los Angeles,CA,90017,US,34.0494,-118.2588,777 S Figueroa St, Los Angeles, CA 90017
ID032,User 32,801 S Figueroa St,,Los Angeles,CA,90017,US,34.0478,-118.2594,801 S Figueroa St, Los Angeles, CA 90017
ID033,User 33,915 Wilshire Blvd,,Los Angeles,CA,90017,US,34.0487,-118.2573,915 Wilshire Blvd, Los Angeles, CA 90017
ID034,User 34,700 Wilshire Blvd,,Los Angeles,CA,90017,US,34.0482,-118.2570,700 Wilshire Blvd, Los Angeles, CA 90017
ID035,User 35,523 W 6th St,,Los Angeles,CA,90014,US,34.0465,-118.2536,523 W 6th St, Los Angeles, CA 90014
ID036,User 36,621 S Spring St,,Los Angeles,CA,90014,US,34.0441,-118.2513,621 S Spring St, Los Angeles, CA 90014
ID037,User 37,548 S Spring St,,Los Angeles,CA,90013,US,34.0459,-118.2505,548 S Spring St, Los Angeles, CA 90013
ID038,User 38,453 S Spring St,,Los Angeles,CA,90013,US,34.0475,-118.2497,453 S Spring St, Los Angeles, CA 90013
ID039,User 39,312 W 5th St,,Los Angeles,CA,90013,US,34.0479,-118.2490,312 W 5th St, Los Angeles, CA 90013
ID040,User 40,221 W 6th St,,Los Angeles,CA,90014,US,34.0456,-118.2520,221 W 6th St, Los Angeles, CA 90014
ID041,User 41,100 S Main St,,Los Angeles,CA,90012,US,34.0505,-118.2435,100 S Main St, Los Angeles, CA 90012
ID042,User 42,200 N Spring St,,Los Angeles,CA,90012,US,34.0537,-118.2427,200 N Spring St, Los Angeles, CA 90012
ID043,User 43,300 N Los Angeles St,,Los Angeles,CA,90012,US,34.0531,-118.2440,300 N Los Angeles St, Los Angeles, CA 90012
ID044,User 44,111 N Hope St,,Los Angeles,CA,90012,US,34.0560,-118.2467,111 N Hope St, Los Angeles, CA 90012
ID045,User 45,350 S Figueroa St,,Los Angeles,CA,90071,US,34.0543,-118.2541,350 S Figueroa St, Los Angeles, CA 90071
ID046,User 46,201 N Figueroa St,,Los Angeles,CA,90012,US,34.0573,-118.2472,201 N Figueroa St, Los Angeles, CA 90012
ID047,User 47,300 S Grand Ave,,Los Angeles,CA,90071,US,34.0508,-118.2510,300 S Grand Ave, Los Angeles, CA 90071
ID048,User 48,600 W 7th St,,Los Angeles,CA,90017,US,34.0472,-118.2575,600 W 7th St, Los Angeles, CA 90017
ID049,User 49,811 Wilshire Blvd,,Los Angeles,CA,90017,US,34.0489,-118.2571,811 Wilshire Blvd, Los Angeles, CA 90017
ID050,User 50,550 S Hope St,,Los Angeles,CA,90071,US,34.0530,-118.2550,550 S Hope St, Los Angeles, CA 90071
ID051,User 51,233 S Wacker Dr,,Chicago,IL,60606,US,41.8789,-87.6359,233 S Wacker Dr, Chicago, IL 60606
ID052,User 52,200 S Wacker Dr,,Chicago,IL,60606,US,41.8795,-87.6360,200 S Wacker Dr, Chicago, IL 60606
ID053,User 53,111 S Wacker Dr,,Chicago,IL,60606,US,41.8812,-87.6360,111 S Wacker Dr, Chicago, IL 60606
ID054,User 54,300 S Riverside Plaza,,Chicago,IL,60606,US,41.8778,-87.6385,300 S Riverside Plaza, Chicago, IL 60606
ID055,User 55,10 S Riverside Plaza,,Chicago,IL,60606,US,41.8817,-87.6383,10 S Riverside Plaza, Chicago, IL 60606
ID056,User 56,311 S Wacker Dr,,Chicago,IL,60606,US,41.8772,-87.6360,311 S Wacker Dr, Chicago, IL 60606
ID057,User 57,500 W Madison St,,Chicago,IL,60661,US,41.8829,-87.6433,500 W Madison St, Chicago, IL 60661
ID058,User 58,150 S Wacker Dr,,Chicago,IL,60606,US,41.8804,-87.6360,150 S Wacker Dr, Chicago, IL 60606
ID059,User 59,101 N Wacker Dr,,Chicago,IL,60606,US,41.8847,-87.6363,101 N Wacker Dr, Chicago, IL 60606
ID060,User 60,300 N LaSalle St,,Chicago,IL,60654,US,41.8887,-87.6335,300 N LaSalle St, Chicago, IL 60654
ID061,User 61,150 N Riverside Plaza,,Chicago,IL,60606,US,41.8856,-87.6381,150 N Riverside Plaza, Chicago, IL 60606
ID062,User 62,350 N Orleans St,,Chicago,IL,60654,US,41.8893,-87.6365,350 N Orleans St, Chicago, IL 60654
ID063,User 63,222 N LaSalle St,,Chicago,IL,60601,US,41.8872,-87.6330,222 N LaSalle St, Chicago, IL 60601
ID064,User 64,130 E Randolph St,,Chicago,IL,60601,US,41.8845,-87.6225,130 E Randolph St, Chicago, IL 60601
ID065,User 65,200 E Randolph St,,Chicago,IL,60601,US,41.8850,-87.6219,200 E Randolph St, Chicago, IL 60601
ID066,User 66,500 E North Water St,,Chicago,IL,60611,US,41.8895,-87.6163,500 E North Water St, Chicago, IL 60611
ID067,User 67,401 N Michigan Ave,,Chicago,IL,60611,US,41.8892,-87.6241,401 N Michigan Ave, Chicago, IL 60611
ID068,User 68,435 N Michigan Ave,,Chicago,IL,60611,US,41.8897,-87.6238,435 N Michigan Ave, Chicago, IL 60611
ID069,User 69,500 N Michigan Ave,,Chicago,IL,60611,US,41.8906,-87.6238,500 N Michigan Ave, Chicago, IL 60611
ID070,User 70,600 N Michigan Ave,,Chicago,IL,60611,US,41.8926,-87.6240,600 N Michigan Ave, Chicago, IL 60611
ID071,User 71,875 N Michigan Ave,,Chicago,IL,60611,US,41.8988,-87.6243,875 N Michigan Ave, Chicago, IL 60611
ID072,User 72,737 N Michigan Ave,,Chicago,IL,60611,US,41.8953,-87.6241,737 N Michigan Ave, Chicago, IL 60611
ID073,User 73,111 S Michigan Ave,,Chicago,IL,60603,US,41.8797,-87.6247,111 S Michigan Ave, Chicago, IL 60603
ID074,User 74,122 S Michigan Ave,,Chicago,IL,60603,US,41.8787,-87.6244,122 S Michigan Ave, Chicago, IL 60603
ID075,User 75,224 S Michigan Ave,,Chicago,IL,60604,US,41.8770,-87.6242,224 S Michigan Ave, Chicago, IL 60604
ID076,User 76,800 Bell St,,Houston,TX,77002,US,29.7562,-95.3678,800 Bell St, Houston, TX 77002
ID077,User 77,910 Louisiana St,,Houston,TX,77002,US,29.7580,-95.3670,910 Louisiana St, Houston, TX 77002
ID078,User 78,1000 Louisiana St,,Houston,TX,77002,US,29.7589,-95.3673,1000 Louisiana St, Houston, TX 77002
ID079,User 79,1100 Louisiana St,,Houston,TX,77002,US,29.7598,-95.3677,1100 Louisiana St, Houston, TX 77002
ID080,User 80,1201 Louisiana St,,Houston,TX,77002,US,29.7607,-95.3680,1201 Louisiana St, Houston, TX 77002
ID081,User 81,1401 McKinney St,,Houston,TX,77010,US,29.7578,-95.3622,1401 McKinney St, Houston, TX 77010
ID082,User 82,1500 Louisiana St,,Houston,TX,77002,US,29.7628,-95.3688,1500 Louisiana St, Houston, TX 77002
ID083,User 83,711 Louisiana St,,Houston,TX,77002,US,29.7559,-95.3662,711 Louisiana St, Houston, TX 77002
ID084,User 84,600 Travis St,,Houston,TX,77002,US,29.7588,-95.3638,600 Travis St, Houston, TX 77002
ID085,User 85,700 Milam St,,Houston,TX,77002,US,29.7602,-95.3650,700 Milam St, Houston, TX 77002
ID086,User 86,909 Fannin St,,Houston,TX,77010,US,29.7554,-95.3625,909 Fannin St, Houston, TX 77010
ID087,User 87,1001 Fannin St,,Houston,TX,77002,US,29.7568,-95.3633,1001 Fannin St, Houston, TX 77002
ID088,User 88,1111 Bagby St,,Houston,TX,77002,US,29.7593,-95.3708,1111 Bagby St, Houston, TX 77002
ID089,User 89,1200 Smith St,,Houston,TX,77002,US,29.7610,-95.3692,1200 Smith St, Houston, TX 77002
ID090,User 90,1301 McKinney St,,Houston,TX,77010,US,29.7573,-95.3630,1301 McKinney St, Houston, TX 77010
ID091,User 91,1000 Main St,,Houston,TX,77002,US,29.7582,-95.3644,1000 Main St, Houston, TX 77002
ID092,User 92,1100 Milam St,,Houston,TX,77002,US,29.7623,-95.3668,1100 Milam St, Houston, TX 77002
ID093,User 93,4200 Westheimer Rd,,Houston,TX,77027,US,29.7405,-95.4452,4200 Westheimer Rd, Houston, TX 77027
ID094,User 94,5000 Westheimer Rd,,Houston,TX,77056,US,29.7410,-95.4610,5000 Westheimer Rd, Houston, TX 77056
ID095,User 95,5100 Westheimer Rd,,Houston,TX,77056,US,29.7412,-95.4625,5100 Westheimer Rd, Houston, TX 77056
ID096,User 96,1700 Post Oak Blvd,,Houston,TX,77056,US,29.7460,-95.4620,1700 Post Oak Blvd, Houston, TX 77056
ID097,User 97,1800 Post Oak Blvd,,Houston,TX,77056,US,29.7475,-95.4622,1800 Post Oak Blvd, Houston, TX 77056
ID098,User 98,2400 Westheimer Rd,,Houston,TX,77098,US,29.7420,-95.4190,2400 Westheimer Rd, Houston, TX 77098
ID099,User 99,3000 Westheimer Rd,,Houston,TX,77098,US,29.7415,-95.4310,3000 Westheimer Rd, Houston, TX 77098
ID100,User 100,2000 Westheimer Rd,,Houston,TX,77098,US,29.7423,-95.4120,2000 Westheimer Rd, Houston, TX 77098
ID101,User 101,400 Pine St,,Seattle,WA,98101,US,47.6101,-122.3381,400 Pine St, Seattle, WA 98101
ID102,User 102,500 Pine St,,Seattle,WA,98101,US,47.6108,-122.3365,500 Pine St, Seattle, WA 98101
ID103,User 103,600 Pine St,,Seattle,WA,98101,US,47.6115,-122.3350,600 Pine St, Seattle, WA 98101
ID104,User 104,700 Pine St,,Seattle,WA,98101,US,47.6121,-122.3333,700 Pine St, Seattle, WA 98101
ID105,User 105,1501 4th Ave,,Seattle,WA,98101,US,47.6105,-122.3360,1501 4th Ave, Seattle, WA 98101
ID106,User 106,1601 5th Ave,,Seattle,WA,98101,US,47.6112,-122.3345,1601 5th Ave, Seattle, WA 98101
ID107,User 107,1700 7th Ave,,Seattle,WA,98101,US,47.6128,-122.3340,1700 7th Ave, Seattle, WA 98101
ID108,User 108,1201 3rd Ave,,Seattle,WA,98101,US,47.6067,-122.3362,1201 3rd Ave, Seattle, WA 98101
ID109,User 109,999 3rd Ave,,Seattle,WA,98104,US,47.6055,-122.3348,999 3rd Ave, Seattle, WA 98104
ID110,User 110,701 5th Ave,,Seattle,WA,98104,US,47.6047,-122.3315,701 5th Ave, Seattle, WA 98104
ID111,User 111,801 2nd Ave,,Seattle,WA,98104,US,47.6035,-122.3330,801 2nd Ave, Seattle, WA 98104
ID112,User 112,901 5th Ave,,Seattle,WA,98164,US,47.6062,-122.3310,901 5th Ave, Seattle, WA 98164
ID113,User 113,601 5th Ave,,Seattle,WA,98104,US,47.6038,-122.3322,601 5th Ave, Seattle, WA 98104
ID114,User 114,1301 5th Ave,,Seattle,WA,98101,US,47.6095,-122.3342,1301 5th Ave, Seattle, WA 98101
ID115,User 115,1420 5th Ave,,Seattle,WA,98101,US,47.6102,-122.3338,1420 5th Ave, Seattle, WA 98101
ID116,User 116,2001 6th Ave,,Seattle,WA,98121,US,47.6138,-122.3402,2001 6th Ave, Seattle, WA 98121
ID117,User 117,2100 4th Ave,,Seattle,WA,98121,US,47.6145,-122.3418,2100 4th Ave, Seattle, WA 98121
ID118,User 118,2201 Westlake Ave,,Seattle,WA,98121,US,47.6162,-122.3425,2201 Westlake Ave, Seattle, WA 98121
ID119,User 119,1918 8th Ave,,Seattle,WA,98101,US,47.6140,-122.3370,1918 8th Ave, Seattle, WA 98101
ID120,User 120,2200 6th Ave,,Seattle,WA,98121,US,47.6155,-122.3410,2200 6th Ave, Seattle, WA 98121
ID121,User 121,1122 4th Ave,,Seattle,WA,98101,US,47.6075,-122.3355,1122 4th Ave, Seattle, WA 98101
ID122,User 122,1000 2nd Ave,,Seattle,WA,98104,US,47.6058,-122.3335,1000 2nd Ave, Seattle, WA 98104
ID123,User 123,1001 4th Ave,,Seattle,WA,98154,US,47.6068,-122.3345,1001 4th Ave, Seattle, WA 98154
ID124,User 124,1200 5th Ave,,Seattle,WA,98101,US,47.6088,-122.3340,1200 5th Ave, Seattle, WA 98101
ID125,User 125,1301 3rd Ave,,Seattle,WA,98101,US,47.6072,-122.3365,1301 3rd Ave, Seattle, WA 98101"""

  lines = csv_data.strip().split("\n")
  headers = lines[0].split(",")

  for line in lines[1:]:
    # Simple CSV row parser keeping quotes/commas in mind if needed, 
    # or split by comma for this clean dataset:
    values = line.split(",")
    row_dict = dict(zip(headers, values))

    # Convert types where necessary
    row_dict['latitude'] = float(row_dict['latitude'])
    row_dict['longitude'] = float(row_dict['longitude'])

    # Check if record already exists by ID to prevent duplicating on multiple runs
    existing = app_tables.mapitems.get(id=row_dict['id'])
    if not existing:
      app_tables.mapitems.add_row(**row_dict)

  return "Successfully seeded 125 test records!"