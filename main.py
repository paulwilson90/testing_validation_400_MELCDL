import pandas as pd
from math import radians, sin
import re
from calcs import get_uld, ice_protect_addit, company_addit_dry_wet, get_wat_limit, final_max_weight, get_v_speeds
from calcs import slope_corrected, vapp_corrections, reduced_np_addit, wind_correct_formulated, max_landing_wt_lda
from calcs import abnormal_factor

"""To auto space the columns in Excel: right click worksheet, view code, dropdown to worksheet and type:"""
""" Cells.EntireColumn.AutoFit """

"""
ULD
Wind, Slope
V-App
Red NP
Ice 
MEL - This is ULD
Company wet/dry
"""

xls = pd.ExcelFile('Q400 MELCDL Test Cases.xlsx')
Q400 = pd.read_excel(xls, 'Q400 MELCDL')

all_excel_data = {"Test Case Number": [], "Airport Code": [], "Destination": [], "Runway": [],
                  "Elevation": [], "LDA": [], "Slope": [], "Grooved/Ungrooved": [], "Wind Direction": [],
                  "Wind Speed": [], '"HW (+) / TW (-) Comp"': [], "Temp": [], "QNH": [], "Dry/Wet": [],
                  "Weight": [], "VREF Additive": [], "Flaps": [], "Bleeds": [], "Power": [],
                  "Ice protection": [], "Pressure Altitude": [], "Abnormality": [], "Factor Applied": [],
                  "MLDW": [], "Unfactored ULD": [], "ULD": [], "LDR": [], "LDR Ice": [], "Vapp": [],
                  "VREF": [], "VREF ICE": []}


def all_data(all_row_data):
    """Store all the headings from the Excel file
    :arg all_row_data which is each heading item from each row"""
    test_case_number = all_row_data['Test Case Number']
    airport_code = all_row_data['Airport Code']
    destination = all_row_data['Destination']
    runway = all_row_data['Runway']
    elevation = all_row_data['Elevation']
    lda = all_row_data['LDA']
    slope = all_row_data['Slope']
    grooved_ungrooved = all_row_data['Grooved/Ungrooved']
    wind_direction = all_row_data['Wind Direction']
    wind_speed = all_row_data['Wind Speed']
    head_tail = all_row_data['HW (+) / \nTW (-) Comp']
    temp = int(all_row_data['Temp'])
    qnh = all_row_data['QNH']
    wet_dry = all_row_data['Dry/Wet']
    weight = all_row_data['Weight']
    vref_addit = all_row_data['VREF Additive']
    flap = all_row_data['Flaps']
    flap = int(flap)
    bleeds = all_row_data['Bleeds']
    power = all_row_data['Power']
    ice = all_row_data['Ice protection']
    ab_fctr = all_row_data['MELCDL']

    pressure_altitude = (elevation + ((1013 - qnh) * 30))
    elevation = elevation / 1000

    str_rwy = str(runway)
    check_ = re.search("\d\d", str_rwy)
    if not check_:
        str_rwy = "0" + str_rwy

    cross_runway = int(re.search("\d\d", str_rwy).group()) * 10
    radian = radians(cross_runway - wind_direction)
    crosswind = abs(round(sin(radian) * wind_speed))

    final_uld = get_uld(elevation, flap, weight)
    print("Flap", flap, "Weight", weight, "Bleed", bleeds,
          "Elev", int(elevation * 1000), "Temp", temp, "QNH", qnh, "ULD", final_uld, "Test case",
          test_case_number)

    wind_formula_ULD, tail_more_than_10 = wind_correct_formulated(final_uld, head_tail)
    print(head_tail, "WIND COMP", wind_formula_ULD, "CORRECTED FOR WIND")

    corrected_for_slope = int(slope_corrected(slope, wind_formula_ULD))
    print(slope, "SLOPE giving", corrected_for_slope, "CORRECTED FOR SLOPE")

    vapp, vref, vref_ice = get_v_speeds(weight, flap, vref_addit, ice)
    print("V SPEEDS", vapp, vref, vref_ice)

    corrected_for_vapp, percent_increase = vapp_corrections(corrected_for_slope, vref, vref_addit)

    corrected_for_prop = reduced_np_addit(power, corrected_for_vapp)
    print("PROP", power, corrected_for_prop, "LD WITH 6% ADD at if RDCP")

    # Set into variables the ice ON and ice OFF distances regardless of ice conditions
    ICE_OFF_not_company_corrected = corrected_for_prop
    ICE_ON_not_company_corrected = ice_protect_addit(flap, corrected_for_prop) / percent_increase  # take off VAPP addit
    print("The ice added distance is", ICE_ON_not_company_corrected, "compared to the ice off distance of",
          ICE_OFF_not_company_corrected)

    # take the ice ON and ice OFF distances and apply the abnormal factor to both
    distance_ab_fctr_added, ice_distance_ab_fctr_added, abnormal_multiplier, can_land_in_this_config = abnormal_factor(
        ab_fctr, ICE_OFF_not_company_corrected, ICE_ON_not_company_corrected, bleeds, ice, tail_more_than_10, power)

    # determine which ULD to provide on the Excel sheet. This is the final distance before operational addit and is
    # Purely to give the Excel sheet the ULD, ...........it is not used again..............
    if ice == "On":
        ULD_final_before_company = int(ice_distance_ab_fctr_added)
    else:
        ULD_final_before_company = int(distance_ab_fctr_added)

    # Add company operational factor to the ice ON and ice OFF distance
    LDR_ICE, LDR = company_addit_dry_wet(wet_dry,
                                         ice_on_ld=ice_distance_ab_fctr_added,
                                         ice_off_ld=distance_ab_fctr_added)

    print("The runway is", wet_dry, "Giving", LDR_ICE, "as LDR ICE", LDR, "LDR")

    max_wat_weight, off_chart, MLDW = get_wat_limit(temp, flap, power, bleeds, pressure_altitude,
                                                    test_case_number, ab_fctr)
    print("BLEEDS", bleeds, "TEMP", temp, "PRESS ALT", pressure_altitude, "Max WAT weight", max_wat_weight)

    max_field_based_wt = max_landing_wt_lda(lda, ice, LDR_ICE, LDR, flap, weight, final_uld)

    max_weight = final_max_weight(max_wat_weight, max_field_based_wt, MLDW, off_chart)

    if head_tail < -10:
        head_tail = str(head_tail) + '*'
    if crosswind > 32:
        wind_speed = str(wind_speed) + f" XW is {crosswind}*"  # Will make the wind component field go red

    #  NSW inop has a limit on crosswind of 25kt.
    if ab_fctr == "INOP1 (NWS)":
        if crosswind > 25:
            wind_speed = str(wind_speed) + f" XW is {crosswind}*"  # Will make the wind component field go red
            can_land_in_this_config = False

    all_excel_data["Test Case Number"].append(test_case_number)
    all_excel_data["Airport Code"].append(airport_code)
    all_excel_data["Destination"].append(destination)
    all_excel_data["Runway"].append(runway)
    all_excel_data["Elevation"].append(elevation * 1000)
    all_excel_data["LDA"].append(lda)
    all_excel_data["Slope"].append(slope)
    all_excel_data["Grooved/Ungrooved"].append(grooved_ungrooved)
    all_excel_data["Wind Direction"].append(wind_direction)
    all_excel_data["Wind Speed"].append(wind_speed)
    all_excel_data['"HW (+) / TW (-) Comp"'].append(head_tail)
    all_excel_data["Temp"].append(temp)
    all_excel_data["QNH"].append(qnh)
    all_excel_data["Dry/Wet"].append(wet_dry)
    all_excel_data["Weight"].append(weight)
    all_excel_data["VREF Additive"].append(vref_addit)
    all_excel_data["Flaps"].append(flap)
    all_excel_data["Bleeds"].append(bleeds)
    all_excel_data["Power"].append(power)
    all_excel_data["Ice protection"].append(ice)
    all_excel_data["Pressure Altitude"].append(pressure_altitude)

    if not can_land_in_this_config:  # due to the config being not allowed for particular non normal
        ab_fctr = ab_fctr + "*"  # Will make the non-normal field go red
        abnormal_multiplier = pd.NA
        max_weight = pd.NA
        final_uld = pd.NA
        ULD_final_before_company = pd.NA
        LDR = pd.NA
        LDR_ICE = pd.NA
        vapp = pd.NA
        vref = pd.NA
        vref_ice = pd.NA

    all_excel_data["Abnormality"].append(ab_fctr)
    all_excel_data["Factor Applied"].append(abnormal_multiplier)

    all_excel_data["MLDW"].append(max_weight)
    all_excel_data["Unfactored ULD"].append(final_uld)
    all_excel_data["ULD"].append(ULD_final_before_company)  # will be either corrected for ice or not depends on ice
    all_excel_data["LDR"].append(LDR)
    all_excel_data["LDR Ice"].append(LDR_ICE)

    all_excel_data["Vapp"].append(vapp)
    all_excel_data["VREF"].append(vref)
    all_excel_data["VREF ICE"].append(vref_ice)


for row_number in range(len(Q400)):
    all_data(Q400.loc[row_number])


def write_to_excel(all_exc):
    # Create a Pandas Excel writer using XlsxWriter as the engine.
    writer = pd.ExcelWriter('400_MELCDL_RUN.xlsx')
    # Create a Pandas dataframe from the data
    df = pd.DataFrame(all_exc)
    # Convert the dataframe to an XlsxWriter Excel object.
    df = df.style.applymap(lambda x: 'background-color: red' if '*' in str(x) else ('background-color: orange' if
                                                                                    '^' in str(x) else ''))
    df.to_excel(writer, sheet_name='Q400 MELCDL', index=False)
    # Close the Pandas Excel writer and output the Excel file.
    writer.close()


write_to_excel(all_excel_data)
