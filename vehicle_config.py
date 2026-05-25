"""
Vehicle Configuration Parameters

This file contains the default vehicle parameters used by the EV Charging Planner.
Modify these values to match your specific vehicle's specifications.
"""

# Battery capacity in kWh
BATTERY_CAPACITY_KWH = 60.0

# Energy efficiency in kWh per 100 km
EFFICIENCY_KWH_100KM = 17.0

# Charger power rating in kW
CHARGER_POWER_KW = 7.4

# Default daily commute distance in km
DAILY_COMMUTE_KM = 35.0

# Minimum state of charge threshold (%)
MIN_SOC_PERCENT = 30

# Target state of charge for charging slots (%)
TARGET_SOC_PERCENT = 80

# Starting state of charge (%)
START_SOC_PERCENT = 65

# Home location
HOME_LOCATION = "Gent"
