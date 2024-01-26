import json
import math
import pandas as pd

RED = '\033[31m'
REDEND = '\033[0m'


def get_uld(elevation, flap, weight):
    """Gets the ULD by interpolating and using index locations from the QRH
    It grabs the weight one tonne up and below and the elevation INDEX position one up and below.
    It then interpolates using the percentage of the remaining index location."""
    weight_tonnes = weight / 1000
    flap = str(int(flap))
    wt_up = str(math.ceil(float(weight_tonnes)))
    wt_down = str(math.floor(float(weight_tonnes)))
    with open('ulds_q400.json') as ulds:
        uld_ = json.load(ulds)
    elevation_up = math.ceil(elevation)
    elevation_down = math.floor(elevation)
    # interpolating with the upper weight of the two elevation figures
    wt_up_up_data = uld_[flap][wt_up][elevation_up]
    wt_up_dwn_data = uld_[flap][wt_up][elevation_down]
    uld_up_wt = round(wt_up_dwn_data + ((wt_up_up_data - wt_up_dwn_data) * (elevation - elevation_down)))
    # interpolating with the lower weight of the two elevation figures
    wt_dwn_up_data = uld_[flap][wt_down][elevation_up]
    wt_dwn_dwn_data = uld_[flap][wt_down][elevation_down]
    uld_dwn_wt = round(wt_dwn_dwn_data + ((wt_dwn_up_data - wt_dwn_dwn_data) * (elevation - elevation_down)))
    # interpolating for weight between the two elevation interpolated figures
    final_uld = round(uld_dwn_wt + (uld_up_wt - uld_dwn_wt) * (float(weight_tonnes) - int(wt_down)))

    return final_uld


def wind_correct_formulated(ULD, wind_comp):
    """For every ULD entry to the wind chart above 700, add 0.003m on top of 3.8 for every knot head
    for every ULD entry to the wind chart above 700, add 0.01m on top of 12 for every knot tail"""
    tail_more_than_10 = False
    amount_above_700 = ULD - 700
    if wind_comp > 0:  # if its a headwind
        factor_above_uld = amount_above_700 * 0.003
        wind_corrected_ULD = round(ULD - (wind_comp * (3.8 + factor_above_uld)))
    else:  # if its a tailwind
        factor_above_uld = amount_above_700 * 0.01
        wind_corrected_ULD = ULD - round((wind_comp * (12 + factor_above_uld)))

    if wind_comp < -10:  # if the wind is more than 10 knot tail, add 1.6% for every knot over 10t
        tail_more_than_10 = True
        factor_above_uld = amount_above_700 * 0.01
        ten_tail_ULD = ULD - round((-10 * (12 + factor_above_uld)))
        wind_corrected_ULD = int(ten_tail_ULD * (1 + ((abs(wind_comp) - 10) * 1.6) / 100))

    return int(wind_corrected_ULD), tail_more_than_10


def slope_corrected(slope, wind_corrected_ld):
    """If the slope is greater than 0, the slope is going uphill so the distance will be shorter
    IF the slope is less than 0 however, the slope is downhill and the distance increases.
    For every 1% slope downhill (Negative slope), increase the ULD by 9.25% 630
    For every 1% slope uphill (Positive slope), decrease the ULD by 6.5%"""
    #  if the slope is downhill
    if slope < 0:
        slope_correct = wind_corrected_ld + (wind_corrected_ld * (abs(slope) * 0.0925))
    #  if the slope is uphill
    else:
        slope_correct = wind_corrected_ld - (wind_corrected_ld * (abs(slope) * 0.065))
    return slope_correct


def get_v_speeds(weight, flap, vapp_addit, ice):
    flap = str(flap)
    weight = str((math.ceil(weight / 500) * 500) / 1000)
    print(weight)
    with open('ref_speeds.json') as file:
        f = json.load(file)
    vref = f[flap][weight]
    vapp = int(vref) + vapp_addit
    if flap == "15":
        vref_ice = vref + 20
    else:
        vref_ice = vref + 15
    if ice == "On":
        vapp = vref_ice

    return vapp, vref, vref_ice


def vapp_corrections(abnorm_ld, vref, vref_addit):
    """Take the wind and slope corrected landing distance and apply increase in distance by using formula
    vpp^2 / vref^2 which gives the multiplier to the LD"""

    percent_increase = (vref + vref_addit) ** 2 / vref ** 2
    print(f"The Vref additive is {vref_addit} which gives a multiplier of {percent_increase}")

    vapp_adjusted_ld = abnorm_ld * percent_increase
    print(f"Landing distance is now {vapp_adjusted_ld}")

    return vapp_adjusted_ld, percent_increase


def reduced_np_addit(power, vapp_adjusted_ld):
    """Will add the 6% if reduced NP"""
    if power == 'RDCP':
        prop_setting_adjusted = vapp_adjusted_ld * 1.06
    else:
        prop_setting_adjusted = vapp_adjusted_ld

    return int(prop_setting_adjusted)


def ice_protect_addit(flap, prop_adjusted_ld):
    """If INCR REF switch on, add 25% for flap 15 and 20% for flap 35. """
    flap = str(int(flap))
    if flap == "15":
        ice_protect_adjusted_ld = prop_adjusted_ld * 1.25
    else:
        ice_protect_adjusted_ld = prop_adjusted_ld * 1.20

    return ice_protect_adjusted_ld


def company_addit_dry_wet(wet_dry, ice_on_ld, ice_off_ld):
    """Dividing the prop_adjusted_ld by 0.7 if dry and an additional 15% on top of that if wet 1222 = 1465
    """
    if wet_dry == "Wet":
        ICE_ON_wet_dry_adjusted_ld = (ice_on_ld / 0.7) * 1.15
        ICE_OFF_wet_dry_adjusted_ld = (ice_off_ld / 0.7) * 1.15
    else:
        ICE_ON_wet_dry_adjusted_ld = ice_on_ld / 0.7
        ICE_OFF_wet_dry_adjusted_ld = ice_off_ld / 0.7

    return int(ICE_ON_wet_dry_adjusted_ld), int(ICE_OFF_wet_dry_adjusted_ld)


def abnormal_factor(ab_fctr, ICE_OFF_company_applied, ICE_ON_company_applied, bleeds, ice, tail_more_than_10, power):
    """Take in the abnormal factor from the excel sheet and pull its factor from the Multipliers excel sheet
    Return the landing dis required after applying the factor to the distance with all factors applied
    except for company addit. Return BOTH the ice ON and OFF distances.
    Also bypass the EXTENDED DOOR OPEN and EXTENDED DOOR CLOSED factoring as it is a MLDW and WAT issue only"""
    print(ab_fctr, "Is the Abnormality")
    can_land_in_this_config = True
    if ab_fctr == "EXTENDED DOOR OPEN" or ab_fctr == "EXTENDED DOOR CLOSED":  # due to it being WAT and MLDW issue only
        multiplier = 1
        if bleeds == "On" or ice == "On":
            can_land_in_this_config = False
    elif ab_fctr == "INOP (A/S)":
        multiplier = 1.65
        if power == "RDCP":
            can_land_in_this_config = False
    else:  # if the MEL is the NWS
        multiplier = 1
    if tail_more_than_10:  # can't have tail more than 10kt per the supplement compatibility table for any of these MEL
        can_land_in_this_config = False
    distance = ICE_OFF_company_applied * multiplier
    ice_distance = ICE_ON_company_applied * multiplier

    print("Abnormal Multiplier is", multiplier, "which gives a distance of", distance, "ice OFF and", ice_distance,
          "with the ice ON")
    return int(distance), int(ice_distance), multiplier, can_land_in_this_config


def get_torque_limits(temp, pressure_alt, vapp, bleed):
    if temp < 0:
        temp = 0
    if temp > 48:
        temp = 48
    if pressure_alt > 6000:
        pressure_alt = 6000
    if pressure_alt < 0:
        pressure_alt = 0
    temp = str(temp)
    pressure_alt = pressure_alt / 500
    with open(f'takeoff_torques_bleed_{bleed}.json') as file:
        torque = json.load(file)

    elev_up = math.ceil(pressure_alt)
    elev_down = math.floor(pressure_alt)
    temp_up = str(math.ceil(int(temp) / 2) * 2)
    temp_down = str(math.floor(int(temp) / 2) * 2)
    power = ["NTOP", "MTOP"]
    for lst in range(len(power)):
        # interpolating with the upper temp of the two elevation figures
        temp_up_up_data = torque[temp_up][elev_up][lst]
        temp_up_dwn_data = torque[temp_up][elev_down][lst]
        temp_up_wt = temp_up_dwn_data + ((temp_up_up_data - temp_up_dwn_data) * (pressure_alt - elev_down))
        # interpolating with the lower temp of the two elevation figures
        temp_dwn_up_data = torque[temp_down][elev_up][lst]
        temp_dwn_dwn_data = torque[temp_down][elev_down][lst]
        temp_dwn_wt = temp_dwn_dwn_data + ((temp_dwn_up_data - temp_dwn_dwn_data) * (pressure_alt - elev_down))

        torque_limit = (temp_up_wt + temp_dwn_wt) / 2

        power[lst] = torque_limit
    ntop = power[0]
    mtop = power[1]

    if vapp > 100:
        amount_over = vapp - 120
        for_every_three = amount_over / 3
        add_point_one = for_every_three * 0.1
        ntop = ntop + add_point_one
        mtop = mtop + add_point_one

    else:
        amount_under = 120 - vapp
        for_every_three = amount_under / 3
        subtract_point_one = for_every_three * 0.1
        ntop = ntop - subtract_point_one
        mtop = mtop - subtract_point_one

    if ntop > 90.3:
        ntop = 90.3
    if mtop > 100:
        mtop = 100

    return round(ntop, 2), round(mtop, 2)


def get_oei_climb(temp, elev, flap, weight):
    """scale is 0.002 units per dashed line
    Q400"""
    elev = elev * 1000
    weight = weight / 1000
    elevation_envelope = -0.10
    if temp <= 38:
        temp_diff = 38 - temp
        elevation_envelope = temp_diff * 286
    print(elevation_envelope, "Elevation envelope")
    if flap == "15":  # meaning flap 10 missed
        pass
        ref_weight = 22
        weight_change = 0.0058
        if elev > elevation_envelope:
            print("Bottom scale")
            temp_change = 0.00132
            elev_change = 0.0055
            base = 0.133
        else:
            print("Top scale")
            temp_change = 0.00025
            elev_change = 0.0025
            base = 0.093
    else:  # flap 35 missed
        ref_weight = 22
        weight_change = 0.00552
        if elev > elevation_envelope:
            print("Bottom scale")
            temp_change = 0.00134
            elev_change = 0.0056
            base = 0.125
        else:
            print("Top scale")
            temp_change = 0.00026
            elev_change = 0.0025
            base = 0.084

    temp_elev_units = base - (temp * temp_change) - ((elev / 1000) * elev_change)
    print(temp_elev_units, "temp elev")

    variance_from_12t = weight - ref_weight
    weight_units = variance_from_12t * weight_change
    initial_units = temp_elev_units - weight_units
    print(initial_units)

    return round(initial_units * 100, 2)


def get_wat_limit(temp, flap, propeller_rpm, bleed, pressure_alt, test_case, ab_fctr):
    """Take in the temp, flap, bleed position and pressure altitude as parameters
    and return the max landing weight.
    Also trying to keep indexes in range as some temperatures and pressure altitudes are off charts.
    The minimum pressure alt for the chart is 0 and the max is 4000.
    The minimum temperature is 0 and the max is 48, even after the 11 degree addit"""
    off_chart_limits = False

    flap = str(int(flap))
    if pressure_alt < 0:
        pressure_alt = 0
        off_chart_limits = True
    else:
        if pressure_alt > 4000:
            pressure_alt = 4000 / 500
            off_chart_limits = True
        else:
            pressure_alt = pressure_alt / 500
    if propeller_rpm == "RDCP":
        rpm = "850"
    else:
        rpm = "1020"
    if bleed == "On":
        temp = int(temp) + 11

    if temp > 48:
        temp = str(48)
        off_chart_limits = True
        if pressure_alt > 2:
            pressure_alt = 2
    else:
        if temp < 0:
            temp = str(0)
            off_chart_limits = True
        else:
            temp = str(temp)
    if flap == "35":
        ga_flap = "15"
    else:
        ga_flap = "10"

    with open(f'wat_f{ga_flap}.json') as r:
        wat = json.load(r)
    elev_up = math.ceil(pressure_alt)
    elev_down = math.floor(pressure_alt)
    temp_up = str(math.ceil(int(temp) / 2) * 2)
    temp_down = str(math.floor(int(temp) / 2) * 2)

    # interpolating with the upper temp of the two elevation figures
    try:
        temp_up_up_data = wat[rpm][temp_up][elev_up]
    except Exception as err:
        print(RED + "ERROR" + REDEND, err, "TEST CASE", test_case)

    temp_up_dwn_data = wat[rpm][temp_up][elev_down]
    temp_up_wt = round(temp_up_dwn_data + ((temp_up_up_data - temp_up_dwn_data) * (pressure_alt - elev_down)))
    # interpolating with the lower temp of the two elevation figures
    temp_dwn_up_data = wat[rpm][temp_down][elev_up]
    temp_dwn_dwn_data = wat[rpm][temp_down][elev_down]
    temp_dwn_wt = round(temp_dwn_dwn_data + ((temp_dwn_up_data - temp_dwn_dwn_data) * (pressure_alt - elev_down)))

    wat_limit = int((temp_up_wt + temp_dwn_wt) / 2)
    print("WAT limit before abnormal restriction applied", wat_limit)
    MLDW = 28009
    if ab_fctr == "EXTENDED DOOR CLOSED":
        # this is in reference to AFM supplement 7 (Reduction in WAT weight) and
        # Bombardier Service Letter DH8-400-SL-32-001B (Ferry with Gear Doors Open) or the form on comply (MLW)
        if flap == "15":
            MLDW = MLDW - 4655
            wat_limit = wat_limit - 3855
        else:
            MLDW = MLDW - 4200
            wat_limit = wat_limit - 3400
        print("WAT limit after abnormal restriction applied", wat_limit)

    if ab_fctr == "EXTENDED DOOR OPEN":
        if flap == "15":
            MLDW = MLDW - 7600
            wat_limit = wat_limit - 3855
        else:
            MLDW = MLDW - 6700
            wat_limit = wat_limit - 3400
        print("WAT limit after abnormal restriction applied", wat_limit)

    return wat_limit, off_chart_limits, MLDW


def max_landing_wt_lda(lda, ice, ICE_ON_dry_wet, ICE_OFF_dry_wet, flap, weight, unfact_uld):
    """Find the ratio between the landing distance required and the unfactored ULD which returns a multiplier ratio
    Divide the landing distance available by the ratio to find the relative unfactored ULD
    Get the difference between the maximum (LDA based) ULD and the current ULD and divide by 22 for flap 15 or 19 for
    flap 35 and multiply by 1000 (This is ULD diff for every tonne) this will give the weight to add onto the
    current landing weight which will give the max field landing weight. """
    flap = str(flap)
    if ice == "On":
        ld_required = ICE_ON_dry_wet
    else:
        ld_required = ICE_OFF_dry_wet

    if flap == "15":
        ratio = ld_required / unfact_uld
        max_unfact_uld = lda / ratio
        diff_between_ulds = max_unfact_uld - unfact_uld
        final = ((diff_between_ulds / 23) * 1000) + weight
    else:
        ratio = ld_required / unfact_uld
        max_unfact_uld = lda / ratio
        diff_between_ulds = max_unfact_uld - unfact_uld
        final = ((diff_between_ulds / 20.5) * 1000) + weight
    print(int(final), "is the max field based weight")
    return int(final)


def max_brake_energy_wt(flap, temp, elev, weight, head_tail):
    """ example using flap 10...
    for every 50 degrees C, increase by 3.5 units (0.07 per degree). starting at 0 degrees base of 18.5 at sea
    level.
    add 0.75 for every 1000' elevation.
    starting from 22t. every 1t = 2 units
    + 8 for every 10kt tail
    - 5 for every 10 kt tail """
    weight = int(weight) / 1000
    flap = str(flap)
    temp = int(temp)
    elev = int(elev * 1000)
    head_tail = int(head_tail)
    if flap == "10":
        temp_change = 0.07
        base = 18.5
        elev_change = 0.75
        ref_weight = 22
        weight_change = 2
        tail_change = 0.8
        head_change = 0.25
    elif flap == "15":
        temp_change = 0.07
        base = 17.5
        elev_change = 0.65
        ref_weight = 22
        weight_change = 2
        tail_change = 0.7
        head_change = 0.22
    else:
        temp_change = 0.06
        base = 14
        elev_change = 0.6
        ref_weight = 22
        weight_change = 1.7
        tail_change = 0.8
        head_change = 0.26

    temp_elev_units = base + (temp * temp_change) + ((elev / 1000) * elev_change)
    variance_from_22t = weight - ref_weight
    weight_units = variance_from_22t * weight_change
    initial_units = temp_elev_units + weight_units
    if head_tail < 0:
        final_brake_energy = initial_units + (abs(head_tail) * tail_change)
    else:
        final_brake_energy = initial_units - (abs(head_tail) * head_change)
    # print(final_brake_energy, "is the brake energy")
    difference_between_current_and_max = 39.9 - (final_brake_energy)
    max_weight = ref_weight + ((weight_units + difference_between_current_and_max) / weight_change)
    print(int(max_weight * 1000), "Is the max brake energy weight for given conditions")
    return int(max_weight * 1000)


def final_max_weight(max_wat, max_field, max_brake_nrg_weight, MLDW, off_chart):
    """Find and return the lowest weight out of all provided. Also add * to any code where the wat weight
    used a parameter that was off chart."""
    weights = [max_wat, max_field, max_brake_nrg_weight, MLDW]
    # Find the minimum weight
    min_weight = min(weights)

    # Assign the corresponding code
    if min_weight == max_wat:
        code_max = "(c)"
    elif min_weight == max_field:
        code_max = "(f)"
    elif min_weight == max_brake_nrg_weight:
        code_max = "(b)"
    else:
        code_max = "(s)"

    # Add * if off_chart is True
    if off_chart:
        code_max += "*"

    if off_chart:
        max_weight = str(min_weight) + code_max + "^"
    else:
        max_weight = str(min_weight) + code_max
    return max_weight
