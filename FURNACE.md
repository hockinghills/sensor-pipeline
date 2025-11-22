# Furnace Operating Parameters

**THIS IS A GLASS MELTING FURNACE - NOT A PIZZA OVEN**

Raw sensor data is in °C. Grafana displays °F.

## Temperature (furnace_furnace_temp)

| Condition | °C | °F | Notes |
|-----------|----|----|-------|
| **Normal operating** | 1271-1288 | 2320-2350 | Glass melting temp |
| **During charge** | 1204-1288 | 2200-2350 | V-shaped dip, ~150°F drop, 2hr recovery |
| **Idle/maintenance** | ~1038 | ~1900 | Furnace on standby |
| **PROBLEM - too cold** | <1093 | <2000 | Alert: furnace dying |
| **PROBLEM - too hot** | >1316 | >2400 | Alert: overheating |

### Charge Signature
Normal operation shows a distinct pattern when adding glass batch:
1. Sharp temperature drop (~150°F)
2. Gradual 2-hour recovery
3. Back to normal operating temp

This is NORMAL, not a problem.

## Flame Voltage (furnace_flame_voltage)

Scale: 4-10V

| Condition | Voltage | Notes |
|-----------|---------|-------|
| **Normal** | 4-10 V | Healthy flame |
| **PROBLEM** | <4 V | Flame out or pending flame out |
| **PROBLEM** | Erratic | High variance indicates instability |

**Important**: The *range/variance* matters as much as absolute value. Erratic readings indicate potential problems even if within normal voltage range.

## Pressure (inlet/outlet)

**Inlet pressure** (from tank):
- Normal: ~1.4-1.5 PSI
- Below this may indicate tank running low or regulator issue

**Outlet pressure** (at burner):
- May read NEGATIVE due to venturi effect
- Burner design may suck gas faster than supply pressure provides
- Still being characterized

## Temperature Setbacks

When Michael is away, furnace may be intentionally turned down to save fuel:
- **Setback signature**: Steady controlled drop to set point, then hold
- **Different from charge**: Charge is V-shaped dip with recovery

*Mechanism for notating intentional setbacks: TBD*

## Cold Junction (furnace_cold_junction)

Ambient temperature at thermocouple connection point. Used for cold junction compensation.
- Normal: ~15-30°C (room/garage temperature)
- If this is wildly off, thermocouple readings will be inaccurate

---

## Quick Reference

```
Normal:     1280°C / 2340°F  - all good
Charging:   1200°C / 2200°F  - temporary dip, will recover
Standby:    1040°C / 1900°F  - intentional idle
Problem:    <1090°C / <2000°F - furnace is failing
Problem:    >1320°C / >2400°F - overheating
```
