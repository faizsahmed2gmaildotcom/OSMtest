from pyrosm import OSM, get_data
import ee
from uszipcode import SearchEngine
from math import sqrt

yVariable = ["road density", "night brightness"][0]

yearDat = "2018"  # year to fetch income and brightness data from. max for uszipcode is 2018.
city = "tennessee"
zipCodes = ["37201"]  # manually make this list containing all zipcodes of the chosen city
zipCodes.extend([str(p) for p in range(37203, 37222)])
simpleZipQuery = SearchEngine()
comprehensiveZipQuery = SearchEngine(SearchEngine.SimpleOrComprehensiveArgEnum.comprehensive)

variables = {"mean_household_income": [], "median_home_value": [], "housing_units": [], "population": [], "households_with_kids": [], "average_travel_time_to_work_in_minutes": [], "ratio_of_males_to_females": [], "year_housing_was_built": []}
getDensities = ["housing_units", "population"]  # add names of everything that depends on area here
# remove all unknown household income data
popList = []
for var in variables:
    for zci in range(len(zipCodes)):
        simpleZipObj = simpleZipQuery.by_zipcode(zipCodes[zci])
        comprehensiveZipObj = comprehensiveZipQuery.by_zipcode(zipCodes[zci])
        if var == "mean_household_income":
            meanHouseholdIncome = comprehensiveZipObj.average_household_income_over_time[0]["values"]
            addedVal = False
            for mhi in meanHouseholdIncome:
                if mhi['x'] == int(yearDat):
                    variables[var].append(mhi['y'])
                    addedVal = True
                    break
            if not addedVal:
                variables[var].append(None)
                popList.append(zci)
        elif var == "median_home_value":
            variables[var].append(simpleZipObj.median_home_value)
            if simpleZipObj.median_home_value is None:
                popList.append(zci)
        elif var == "housing_units":
            variables[var].append(simpleZipObj.housing_units)
            if simpleZipObj.housing_units is None:
                popList.append(zci)
        elif var == "households_with_kids":
            householdsWithKids = comprehensiveZipObj.households_with_kids[0]["values"][1]['y']
            householdsWithoutKids = comprehensiveZipObj.households_with_kids[0]["values"][0]['y']
            variables[var].append(householdsWithKids / householdsWithoutKids)  # ratio of houses to kids to houses without kids. applies to only occupied houses.
        elif var == "population":
            populationByYear = comprehensiveZipObj.population_by_year[0]["values"]
            addedVal = False
            for pby in populationByYear:
                if pby['x'] == int(yearDat):
                    variables[var].append(pby['y'])
                    addedVal = True
                    break
            if not addedVal:
                variables[var].append(None)
                popList.append(zci)
        elif var == "average_travel_time_to_work_in_minutes":
            travelTimeAmount = [times['y'] for times in comprehensiveZipObj.travel_time_to_work_in_minutes[0]["values"]]
            travelTimes = [4.5, 14.5, 24.5, 34.5, 42.0, 52.0, 74.5, 104.5]
            variables[var].append(sum(travelTimeAmount[t] * travelTimes[t] for t in range(len(travelTimeAmount))) / sum(travelTimeAmount))  # average travel time in minutes
        elif var == "ratio_of_males_to_females":
            variables[var].append(comprehensiveZipObj.population_by_gender[0]["values"][0]['y'] / comprehensiveZipObj.population_by_gender[0]["values"][1]['y'])  # ratio of males to females
        elif var == "year_housing_was_built":
            housingYearData = [years['y'] for years in comprehensiveZipObj.year_housing_was_built[0]["values"]]
            housingYears = [hy for hy in range(len(housingYearData))]  # normalized representation where 1935 is 0 and 2015 is 8
            variables[var].append(sum(housingYearData[y] * housingYears[y] for y in range(len(housingYearData))) / sum(housingYearData))  # average house age

# remove all zipcode data with no available data for any variable. also applies to empty data by year from comprehensiveZipObj.
popList = list(dict.fromkeys(popList))
popList.sort(reverse=True)  # prevent later values' indexes from decrementation
for p in popList:
    zipCodes.pop(p)
    for var in variables:
        variables[var].pop(p)

yVariableData = [0 for _ in zipCodes]
zipBounds = [simpleZipQuery.by_zipcode(zc).bounds for zc in zipCodes]  # westmost, eastmost, northmost, southmost points of each zipcode area
zipAreas = [abs((za["east"] - za["west"]) * (za["north"] - za["south"])) for za in zipBounds]
cityBounds = [min(b["west"] for b in zipBounds), min(b["south"] for b in zipBounds), max(b["east"] for b in zipBounds), max(b["north"] for b in zipBounds)]
for d in getDensities:
    for zaI in range(len(zipAreas)):
        variables[d][zaI] /= zipAreas[zaI]

if yVariable == "road density":
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
                    yVariableData[zbi] += 1
                    break

    yVariableData = [yVariableData[rd] / zipAreas[rd] for rd in range(len(yVariableData))]  # make road density dependent on area

elif yVariable == "night brightness":
    def getAvgRadiance(img):
        return img.reduceRegions(reducer=ee.Reducer.mean(), collection=currentBound, scale=500)


    ee.Authenticate()
    ee.Initialize(project="nightbrightness")

    for zI in range(len(zipBounds)):
        zipBound = zipBounds[zI]
        currentBound = ee.Geometry.BBox(zipBound["west"], zipBound["south"], zipBound["east"], zipBound["north"])
        zipImage = ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG").filterBounds(currentBound).filterDate(yearDat).select("avg_rad").map(getAvgRadiance)
        zipImage = zipImage.toList(zipImage.size())
        yVariableData[zI] = ee.Image(zipImage.get(-1)).getInfo()["features"][0]["properties"]["mean"]  # get the latest mean radiance data of every zipcode

PCC = {v: 0.0 for v in variables.keys()}
# get the Pearson correlation coefficient with x = variablesData[varI] and y = yVariable
yVariableDataAvg = sum(yVariableData) / len(yVariableData)
for varName in variables.keys():
    avgVarData = sum(variables[varName]) / len(variables[varName])
    PCC[varName] = sum((variables[varName][i] - avgVarData) * (yVariableData[i] - yVariableDataAvg) for i in range(len(variables[varName]))) / sqrt(sum((variables[varName][i] - avgVarData) ** 2 for i in range(len(variables[varName]))) * sum((yVariableData[i] - yVariableDataAvg) ** 2 for i in range(len(variables[varName]))))
for k in PCC.keys():
    if k in getDensities:
        print(f"{k.replace('_', ' ').capitalize()} (density): {PCC[k]}")
    else:
        print(f"{k.replace('_', ' ').capitalize()}: {PCC[k]}")
