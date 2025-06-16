import ee
from uszipcode import SearchEngine
from math import sqrt

ee.Authenticate()
ee.Initialize(project="nightbrightness")

yearDat = "2018"  # year to fetch income and brightness data from. max for uszipcode is 2018.
city = "tennessee"
zipCodes = ["37201"]  # manually make this list containing all zipcodes of the chosen city
zipCodes.extend([str(p) for p in range(37203, 37222)])
simpleZipQuery = SearchEngine()
comprehensiveZipQuery = SearchEngine(SearchEngine.SimpleOrComprehensiveArgEnum.comprehensive)

variables = ["mean_household_income", "median_home_value", "housing_units", "population", "households_with_kids", "travel_time_to_work_in_minutes", "males_to_females", "year_housing_was_built"]
variablesData = []
# remove all unknown household income data
for var in variables:
    popList = []
    variablesData.append([])
    for zci in range(len(zipCodes)):
        simpleZipObj = simpleZipQuery.by_zipcode(zipCodes[zci])
        comprehensiveZipObj = comprehensiveZipQuery.by_zipcode(zipCodes[zci])
        if var == "mean_household_income":
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
        elif var == "males_to_females":
            variablesData[-1].append(comprehensiveZipObj.population_by_gender[0]["values"][0]['y'] / comprehensiveZipObj.population_by_gender[0]["values"][1]['y'])  # ratio of males to females
        elif var == "year_housing_was_built":
            housingYearData = [years['y'] for years in comprehensiveZipObj.year_housing_was_built[0]["values"]]
            housingYears = [hy for hy in range(len(housingYearData))]  # normalized representation where 1935 is 0 and 2015 is 8
            variablesData[-1].append(sum(housingYearData[y] * housingYears[y] for y in range(len(housingYearData))) / sum(housingYearData))  # average house age

    popList.reverse()  # prevent later values' indexes from decrementation
    for p in popList:
        zipCodes.pop(p)

nightBrightness = [0 for _ in zipCodes]
zipBounds = [simpleZipQuery.by_zipcode(zc).bounds for zc in zipCodes]  # westmost, eastmost, northmost, southmost points of each zipcode area
cityBounds = [min(b["west"] for b in zipBounds), min(b["south"] for b in zipBounds), max(b["east"] for b in zipBounds), max(b["north"] for b in zipBounds)]


def getAvgRadiance(img):
    return img.reduceRegions(reducer=ee.Reducer.mean(), collection=currentBound, scale=500)


for zI in range(len(zipBounds)):
    zipBound = zipBounds[zI]
    currentBound = ee.Geometry.BBox(zipBound["west"], zipBound["south"], zipBound["east"], zipBound["north"])
    zipImage = ee.ImageCollection("NOAA/VIIRS/DNB/MONTHLY_V1/VCMCFG").filterBounds(currentBound).filterDate(yearDat).select("avg_rad").map(getAvgRadiance)
    zipImage = zipImage.toList(zipImage.size())
    nightBrightness[zI] = ee.Image(zipImage.get(-1)).getInfo()["features"][0]["properties"]["mean"]  # get the latest mean radiance data of every zipcode

PCC = {v: 0.0 for v in variables}
# get the Pearson correlation coefficient with x = householdIncome and y = radiance
for varI in range(len(variablesData)):
    avgHouseholdIncome = sum(variablesData[varI]) / len(variablesData[varI])
    avgPostalRadiance = sum(nightBrightness) / len(nightBrightness)
    PCC[variables[varI]] = sum((variablesData[varI][i] - avgHouseholdIncome) * (nightBrightness[i] - avgPostalRadiance) for i in range(len(variablesData[varI]))) / sqrt(sum((variablesData[varI][i] - avgHouseholdIncome) ** 2 for i in range(len(variablesData[varI]))) * sum((nightBrightness[i] - avgPostalRadiance) ** 2 for i in range(len(variablesData[varI]))))
for k in PCC.keys():
    print(f"{k.replace('_', ' ').capitalize()}: {PCC[k]}")
