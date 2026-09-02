"""XGBoost yield-prediction baseline - see random_forest.py for why this
comparison is required, not optional."""

from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, r2_score

from evaluation.baselines.features import build_feature_matrix
from training.dataset import SeasonExample


def train_and_eval(train_examples: list[SeasonExample], test_examples: list[SeasonExample]) -> dict:
    X_train, y_train = build_feature_matrix(train_examples)
    X_test, y_test = build_feature_matrix(test_examples)

    model = XGBRegressor(n_estimators=300, max_depth=4, learning_rate=0.05, random_state=0)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)

    # r2_score is undefined (near-meaningless) when y_test has ~zero variance,
    # which is the current case for the real Coimbatore holdout (see
    # data/raw/yield_labels/README.md) - report MAE as the primary metric.
    return {
        "model": "XGBoost (baseline)",
        "mae": mean_absolute_error(y_test, preds),
        "r2": r2_score(y_test, preds),
        "fitted_model": model,
    }
