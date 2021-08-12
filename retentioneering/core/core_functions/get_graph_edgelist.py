# * Copyright (C) 2020 Maxim Godzi, Anatoly Zaytsev, Retentioneering Team
# * This Source Code Form is subject to the terms of the Retentioneering Software Non-Exclusive License (License)
# * By using, sharing or editing this code you agree with the License terms and conditions.
# * You can obtain License text at https://github.com/retentioneering/retentioneering-tools/blob/master/LICENSE.md

import pandas as pd


def get_graph_edgelist(self, *,
                 weight_cols=None,
                 norm_type=None):
    """
    Creates weighted table of the transitions between events.

    Parameters
    ----------
    weight_col: str (optional, default=None)
        Aggregation column for transitions weighting. To calculate weights
        as number of transion events use None. To calculate number
        of unique users passed through given transition 'user_id'.
         For any other aggreagtion, like number of sessions, pass the column name.

    norm_type: {None, 'full', 'node'} (optional, default=None)
        Type of normalization. If None return raw number of transtions
        or other selected aggregation column. 'full' - normalized over
        entire dataset. 'node' weight for edge A --> B normalized over
        user in A

    edge_attributes: str (optional, default 'edge_weight')
        Name for edge_weight columns

    Returns
    -------
    Dataframe with number of rows equal to all transitions with weight
    non-zero weight

    Return type
    -----------
    pd.DataFrame
    """
    if norm_type not in [None, 'full', 'node']:
        raise ValueError(f'unknown normalization type: {norm_type}')

    event_col = self.retention_config['event_col']
    time_col = self.retention_config['event_time_col']

    cols = [event_col, 'next_' + str(event_col)]

    data = self._get_shift().copy()

    default_weight_col = "edge_weight"

    # get aggregation:
    if weight_cols is None:
        agg = (data
               .groupby(cols)[time_col]
               .count()
               .reset_index())
        agg.rename(columns={time_col: default_weight_col}, inplace=True)
    else:
        agg = (data
               .groupby(cols)[time_col]
               .count()
               .reset_index())
        agg.rename(columns={time_col: default_weight_col}, inplace=True)

        for weight_col in weight_cols:
            agg_i = (data
                .groupby(cols)[weight_col]
                .nunique()
                .reset_index())

            agg = agg.join(agg_i[weight_col])

    # apply normalization:
    if norm_type == 'full':
        if weight_col is None:
            agg[default_weight_col] /= agg[default_weight_col].sum()
        else:
            agg[default_weight_col] /= agg[default_weight_col].sum()
            for weight_col in weight_cols:
                agg[weight_col] /= data[weight_col].nunique()

    if norm_type == 'node':
        if weight_col is None:
            event_transitions_counter = data.groupby(event_col)[cols[1]].count().to_dict()
            agg[default_weight_col] /= agg[cols[0]].map(event_transitions_counter)
        else:
            event_transitions_counter = data.groupby(event_col)[cols[1]].count().to_dict()
            agg[default_weight_col] /= agg[cols[0]].map(event_transitions_counter)

            for weight_col in weight_cols:
                user_counter = data.groupby(cols[0])[weight_col].nunique().to_dict()
                agg[weight_col] /= agg[cols[0]].map(user_counter)

    return agg
