from pyrosm import OSM, get_data
from uszipcode import SearchEngine
from math import sqrt

yearDat = "2018"  # year to fetch income data from. max for uszipcode is 2018.
city = "tennessee"
zipCodes = ["37201"]  # manually make this list containing all zipcodes of the chosen city
zipCodes.extend([str(p) for p in range(37203, 37222)])
simpleZipQuery = SearchEngine()
comprehensiveZipQuery = SearchEngine(SearchEngine.SimpleOrComprehensiveArgEnum.comprehensive)

variables = ["mean_household_income", "median_home_value", "housing_units", "households_with_kids", "population", "travel_time_to_work_in_minutes"]
variablesData = []
# remove all unknown household income data
for var in variables:
    popList = []
    variablesData.append([])
    for zci in range(len(zipCodes)):
        simpleZipObj = simpleZipQuery.by_zipcode(zipCodes[zci])
        comprehensiveZipObj = comprehensiveZipQuery.by_zipcode(zipCodes[zci])
        if var == "mean_household_income":  # different to median household income. shows weak positive correlation instead.
            meanHouseholdIncome = comprehensiveZipObj.average_household_income_over_time[0]["values"]
            for mhi in meanHouseholdIncome:
                if mhi['x'] == int(yearDat):
                    variablesData[-1].append(mhi['y'])
                    break
        elif var == "median_home_value":
            if simpleZipObj.median_home_value is not None:
                variablesData[-1].append(simpleZipObj.median_home_value)
            else:
                popList.append(zci)
        elif var == "housing_units":
            if simpleZipObj.housing_units is not None:
                variablesData[-1].append(simpleZipObj.housing_units)
            else:
                popList.append(zci)
        elif var == "households_with_kids":
            householdsWithKids = comprehensiveZipObj.households_with_kids[0]["values"][1]['y']
            if householdsWithKids is not None:
                variablesData[-1].append(householdsWithKids)
            else:
                popList.append(zci)
        elif var == "population":
            if simpleZipObj.population is not None:
                variablesData[-1].append(simpleZipObj.population)
            else:
                popList.append(zci)
        elif var == "travel_time_to_work_in_minutes":
            travelTimeAmount = [times['y'] for times in comprehensiveZipObj.travel_time_to_work_in_minutes[0]["values"]]
            travelTimes = [4.5, 14.5, 24.5, 34.5, 42.0, 52.0, 74.5, 104.5]
            variablesData[-1].append(sum(travelTimeAmount[t] * travelTimes[t] for t in range(len(travelTimeAmount))) / sum(travelTimeAmount))  # average travel time
    popList.reverse()  # prevent later values' indexes from decrementation
    for p in popList:
        zipCodes.pop(p)

roadDensity = [0 for _ in zipCodes]
zipBounds = [simpleZipQuery.by_zipcode(zc).bounds for zc in zipCodes]  # westmost, eastmost, northmost, southmost points of each zipcode area
cityBounds = [min(b["west"] for b in zipBounds), min(b["south"] for b in zipBounds), max(b["east"] for b in zipBounds), max(b["north"] for b in zipBounds)]

mapData = OSM(get_data(city, directory="mapData"), bounding_box=cityBounds)  # import map data
roadData = mapData.get_network(network_type="driving")["geometry"]
for road in roadData:
    # roadPoints: list of points in the current road
    roadPoints = [list(c.coords)[0] for c in list(road.geoms)]
    roadPoints.extend(list(c.coords)[1] for c in list(road.geoms))
    roadPoints = list(dict.fromkeys(roadPoints))  # remove all duplicate points on every road

    """
    POTENTIAL (but extremely unlikely) DATA INACCURACY:
    roads are assumed to NOT be perfectly straight lines for kilometers on end, so that at least one point on a road passing through multiple zip code regions are considered to be inside them all.
    even if some roads are perfectly straight for many kilometers, there are an insignificant amount that intersect through multiple zip code regions without endpoints in either region.
    this greatly alleviates processing power as line-line intersections do not have to be calculated.
    additionally, this prevents potential floating point error from performing arithmetic operations on such large floats.
    """
    for zbi in range(len(zipBounds)):
        for rp in roadPoints:
            # if any road point is inside any zipcode's area, add 1 to that zipcode's area
            if (zipBounds[zbi]["west"] <= rp[0] <= zipBounds[zbi]["east"]) and (zipBounds[zbi]["south"] <= rp[1] <= zipBounds[zbi]["north"]):
                roadDensity[zbi] += 1
                continue

roadDensity = [roadDensity[rd] / abs((zipBounds[rd]["east"] - zipBounds[rd]["west"]) * (zipBounds[rd]["north"] - zipBounds[rd]["south"])) for rd in range(len(roadDensity))]  # make road density dependent on area

print(variablesData)
print(zipBounds)
print(roadDensity)

PCC = {v: 0.0 for v in variables}
# get the Pearson correlation coefficient with x = householdIncome and y = roadDensity
for varI in range(len(variablesData)):
    avgHouseholdIncome = sum(variablesData[varI]) / len(variablesData[varI])
    avgPostalRoads = sum(roadDensity) / len(roadDensity)
    PCC[variables[varI]] = sum((variablesData[varI][i] - avgHouseholdIncome) * (roadDensity[i] - avgPostalRoads) for i in range(len(variablesData[varI]))) / sqrt(sum((variablesData[varI][i] - avgHouseholdIncome) ** 2 for i in range(len(variablesData[varI]))) * sum((roadDensity[i] - avgPostalRoads) ** 2 for i in range(len(variablesData[varI]))))
for k in PCC.keys():
    print(f"{k.replace('_', ' ').capitalize()}: {PCC[k]}")
