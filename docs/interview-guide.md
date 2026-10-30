# Explaining DemandLens in an interview

## A thirty-second explanation

DemandLens forecasts seven days of recorded product sales and turns those forecasts into inventory scenarios. I cleaned transaction data, reconciled unambiguous same-day reversals, compared simple baselines with gradient boosting, and evaluated predictions across historical weekly origins. The app uses SQL analytics and precomputed artifacts so it can run on a small CPU host.

## What exactly is being predicted?

Daily units recorded for established products, after clearly matched same-day cancellations are removed. This is not true unconstrained demand: products may have been unavailable, and the data does not reveal lost purchases.

## Why remove the large cancelled order?

One 74,215-unit storage-jar purchase was reversed 16 minutes later for the same customer, product, quantity, and price. A unique, later, full same-day cancellation provides evidence of reversal. We do not remove an order just because it is large. Partial, cross-day, and ambiguous returns remain separate.

## How do you avoid looking into the future?

At forecast origin D, all sales features use dates before D. Features include prior sales and rolling summaries. Target-date calendar information is known in advance. Training rows are used only when their labels were observable before D. Same-day reversals are complete before the next daily origin; later-day cancellations cannot rewrite earlier sales through this policy.

## Why compare simple methods?

A forecasting model is useful only relative to alternatives. We compare previous-week sales, a trailing mean, a trailing median, a four-week weekday average, and gradient boosting. The median is robust to large spikes and can beat ML. The selected model is the validation winner, not automatically the most complicated one.

## What does WAPE mean?

Sum all absolute prediction errors and divide by total recorded units. Multiply by 100. It is an error measure, not accuracy, and can exceed 100%. MAE gives average daily error in units. Neither metric alone proves a business benefit.

## Is this an untouched test?

No. The first audit exposed a missing median baseline and a reversed order. Those findings motivated the revision, so revised October–December results are retrospective. Within the revised run, validation chooses the model before those outcomes are scored. A stronger generalization claim needs genuinely new data.

## How does the inventory calculation work?

Sum forecast sales over delivery time plus review time, add a user-supplied buffer, and subtract available stock plus eligible inbound minus backorders. Round a positive shortfall up. For 40 expected units, 5 buffer, 20 on hand, and 10 inbound, the order is 15 units. This does not guarantee that stock lasts until delivery or establish an optimal service level.

## What are the biggest limitations?

One old retailer, a selected established-product cohort, uncertain stock availability, promotions absent from the data, difficult wholesale spikes, and limited cancellation matching. Inventory inputs are assumptions. There are no calibrated uncertainty intervals or measured savings.

## What changed after the audit?

We retained the original artifacts, added explicit same-day cancellation reconciliation, rebuilt product selection, added stronger baselines, and documented product/window-level failures. Old and revised scores are not a model-only improvement because the target and product cohort changed.

## Claims to avoid

Do not say WAPE is accuracy, that sales equal all customer demand, that every cancellation is matched, that the revised test is untouched, that ML always wins, or that this project reduced real inventory costs. Quote only the measured results in the current generated experiment report.
