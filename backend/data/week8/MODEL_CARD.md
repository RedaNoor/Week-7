# Week 8 Baseline Model Card

The API trains a deterministic baseline at first use from a maximum random
sample of 30,000 valid listings. The valuation model is a random forest over
one-hot categorical features and normalized numeric features, trained on
log-transformed PKR prices. The lead model is balanced logistic regression
over 4,000 deterministic synthetic leads. Metrics are returned by
`GET /model/info`.

These models demonstrate the Week 8 serving contract. They are not a licensed
valuation, and the lead model must not be used for automated adverse decisions.
The amenity and lead labels are assumptions and require verified production
data, time-based validation, SHAP plots, drift monitoring, and retraining
before deployment.