# Scenario simulator formulas and assumptions

The simulator is a transparent, illustrative case-study model. It is not a
validated financial forecast, procurement optimizer, or statement of RANE's
actual operations.

## Case-study baseline

| Input | Baseline |
|---|---:|
| Revenue | ₹3,421 Cr |
| EBITDA | ₹297.7 Cr |
| EBITDA margin (provided) | 8.7% |
| PAT | ₹37.6 Cr |
| Annual raw-material spend | ₹1,223 Cr |
| OEM cost pass-through | 50% |
| 40-foot container freight | USD 2,172 |
| Annual inbound ocean freight | ₹25 Cr |

These are the values supplied for the case study. The simulator does not infer
or retrieve them from company systems.

## Editable assumptions

The material mix weights are normalized to 100% before use. For each material,
the user can edit the relative mix weight, USD-linked share, tariff exposure,
and illustrative INR/tonne reference cost. The default values are demonstration
assumptions, not observed RANE data or market quotations.

Let:

- \(S_i\): baseline spend for material \(i\), equal to ₹1,223 Cr times its
  normalized mix share.
- \(d\): demand change as a fraction.
- \(p_i\): material price shock as a fraction.
- \(t\): tariff shock as a fraction.
- \(a_i\): editable tariff-exposure fraction.
- \(x\): USD/INR change as a fraction.
- \(u_i\): editable USD-linked share.
- \(r\): OEM cost pass-through fraction.
- \(\tau\): editable tax-rate assumption.

## Raw-material spend

For each material:

```text
Volume-adjusted spend_i = S_i × (1 + d)
Price-adjusted spend_i = Volume-adjusted spend_i × (1 + p_i)
Tariff-adjusted spend_i = Price-adjusted spend_i × (1 + t × a_i)
Scenario spend_i = Tariff-adjusted spend_i × (1 + x × u_i)
```

```text
Scenario raw-material spend = sum(Scenario spend_i)
Incremental material cost = Scenario raw-material spend − ₹1,223 Cr
```

The price, tariff, and foreign-exchange effects are applied once in that order.
The cost bridge is a sequential attribution; interaction effects therefore
follow that displayed order.

## Freight and landed cost

```text
Scenario annual freight
  = ₹25 Cr × (1 + d) × (1 + freight shock) × (1 + x)
Incremental freight cost = Scenario annual freight − ₹25 Cr
```

Freight is modeled separately from raw materials. It is not tariffed and is
not added twice.

Per-tonne reference costs are already entered as illustrative INR/tonne values
at the editable base USD/INR assumption. The landed-cost calculation is:

```text
FX ratio = scenario USD/INR ÷ base USD/INR
Material cost_i / tonne
  = reference cost_i
    × (1 + p_i)
    × (1 + t × a_i)
    × ((1 − u_i) + u_i × FX ratio)
Allocated freight / tonne
  = baseline annual freight ÷ assumed baseline annual tonnes
    × (1 + freight shock) × (1 + x)
Scenario landed cost_i / tonne
  = scenario material cost_i / tonne + allocated freight / tonne
```

Other duties, insurance, handling, grade premiums, and route-specific landed
cost components are not supplied and are not imputed.

## Revenue, EBITDA, and PAT

```text
Scenario revenue = ₹3,421 Cr × (1 + d)
Cost pressure = incremental material cost + incremental freight cost
OEM recovery = max(0, cost pressure) × pass-through rate
Unrecovered cost = cost pressure − OEM recovery
```

To avoid treating the supplied EBITDA margin as a contribution margin while
also separately changing raw-material and freight costs, the demand component
uses this explicit proxy:

```text
Pre-material/pre-freight contribution proxy
  = (₹297.7 Cr EBITDA + ₹1,223 Cr raw materials + ₹25 Cr freight)
    ÷ ₹3,421 Cr revenue
Demand-related EBITDA effect
  = (scenario revenue − ₹3,421 Cr) × contribution proxy
Revised EBITDA
  = ₹297.7 Cr + demand-related EBITDA effect − unrecovered cost
Revised EBITDA margin = revised EBITDA ÷ scenario revenue
Revised PAT
  = ₹37.6 Cr + (revised EBITDA − ₹297.7 Cr) × (1 − tax rate)
```

The PAT formula holds depreciation, financing, and other non-operating items
unchanged. The tax rate is an editable assumption (default 25%); the case-study
inputs do not provide a tax rate or a detailed income statement.

## Inventory runway

The model converts the editable INR/tonne references and ₹1,223 Cr spend into
an illustrative baseline annual tonnage. It then calculates:

```text
Daily scenario consumption = baseline annual tonnes ÷ 365 × (1 + d)
Illustrative current inventory tonnes
  = baseline daily consumption × editable inventory days
Days of cover = current inventory tonnes ÷ daily scenario consumption
Buffer = days of cover − lead-time days − safety-stock days
```

The stock-out runway assumes no replenishment arrives. Inventory, lead time,
and safety stock are not actual RANE records.

## Container model

The USD 2,172 40-foot rate is the case-study baseline. A user-editable 20-foot
cost ratio, 20-foot/40-foot count mix, payload capacities, and payload
utilisation are applied:

```text
Scenario 40-foot rate = USD 2,172 × (1 + freight shock)
Scenario USD/INR = base USD/INR × (1 + x)
20-foot rate = scenario 40-foot rate × editable 20-foot cost ratio
Blended freight/container = weighted 20-foot and 40-foot rates × scenario FX
Container-equivalents = scenario annual freight in INR ÷ blended freight/container
Actual payload/container = editable capacity × editable utilisation
```

Fractional container counts are annualized equivalents, not shipment records.
Material tonnage is allocated using the same normalized illustrative material
mix.

## Division / line cost allocation

No division-level consumption data is supplied. The interface therefore starts
with generic illustrative labels and editable allocation weights; the weights
are normalized to 100%. Material and freight baseline/scenario costs are
allocated proportionally, and the resulting table is marked
`SYNTHETIC_ILLUSTRATIVE_ASSUMPTION`. It is not a measured division cost.

## Action matrix

For each action:

```text
Estimated benefit = applicable modeled exposure × editable mitigation %
Illustrative net impact = estimated benefit − editable implementation cost
```

Actions are sorted by this net-impact assumption. A positive result is not a
validated saving. The app supplies no supplier names or company-specific
functions beyond generic cross-functional review labels.
Expediting and safety-stock benefits are zero unless an inventory-disruption
exposure assumption is entered, because no stock-out-loss evidence was supplied.

## Forecasts and uncertainty

Only sufficiently long, contiguous monthly series with `OFFICIAL_SOURCE_VALUE`
or `OFFICIAL_SOURCE_MATCH_VERIFIED` quality labels are eligible for statistical
forecasting:

- 36 or more months: seasonal naive (12-month lag).
- 12–35 months: simple exponential smoothing (alpha 0.30).
- 6–11 months: linear trend by ordinary least squares.
- Short, unverified, approximate, synthetic, or missing histories: an explicitly
  labeled indexed scenario projection instead of a market forecast.

Statistical intervals are residual-based approximations, not calibrated
confidence guarantees. Scenario bands are user-controlled assumption ranges,
not statistical intervals. Values are indexed to 100 at the latest historical
observation so different currencies and units are not placed on one scale.

