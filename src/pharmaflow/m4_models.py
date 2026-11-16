"""Small CPU baselines; every fitted object receives training rows only."""
import numpy as np
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from .m4_data import run_weights

RULE_FEATURES = ['near_stationary_fraction', 'spanning_arch_now', 'near_speed_mean_m_s',
                 'near_count', 'remaining_count']


def fit_baseline(name, df, columns, config):
    w, prevalence = run_weights(df, balance_classes=False)
    if name == 'constant':
        return dict(name=name, prevalence=prevalence, columns=[])
    if name == 'rule':
        return dict(name=name, columns=RULE_FEATURES)
    numeric = [c for c in columns if c != 'packing_family']
    transformers = [('numeric', StandardScaler(), numeric)]
    if 'packing_family' in columns:
        transformers.append(('packing', OneHotEncoder(handle_unknown='ignore', sparse_output=False), ['packing_family']))
    pre = ColumnTransformer(transformers, remainder='drop', verbose_feature_names_out=False)
    params = dict(config['models'][name])
    if name == 'logistic':
        model = LogisticRegression(random_state=config['seed'], **params)
    elif name == 'forest':
        model = RandomForestClassifier(random_state=config['seed'], n_jobs=config['threads'], **params)
    elif name == 'xgboost':
        from xgboost import XGBClassifier
        model = XGBClassifier(random_state=config['seed'], n_jobs=config['threads'], device='cpu',
                              objective='binary:logistic', eval_metric='logloss', **params)
    else:
        raise ValueError(name)
    pipe = Pipeline([('preprocess', pre), ('model', model)])
    weights, _ = run_weights(df, balance_classes=True)
    pipe.fit(df[columns], df.target, model__sample_weight=weights)
    return dict(name=name, pipeline=pipe, columns=columns, prevalence=prevalence,
                weight_policy='equal-run base weights times training-only balanced-class multipliers')


def predict(artifact, df):
    if artifact['name'] == 'constant':
        return np.full(len(df), artifact['prevalence'])
    if artifact['name'] == 'rule':
        # Fixed, monotone current-observation score, not a calibrated probability.
        score = (.45 * df.near_stationary_fraction.to_numpy()
                 + .35 * df.spanning_arch_now.to_numpy()
                 + .20 * np.exp(-df.near_speed_mean_m_s.to_numpy() / .02))
        return score * ((df.near_count >= 2) & (df.remaining_count >= 2)).to_numpy()
    return artifact['pipeline'].predict_proba(df[artifact['columns']])[:, 1]
