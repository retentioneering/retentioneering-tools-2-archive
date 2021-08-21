# * Copyright (C) 2020 Maxim Godzi, Anatoly Zaytsev, Retentioneering Team
# * This Source Code Form is subject to the terms of the Retentioneering Software Non-Exclusive License (License)
# * By using, sharing or editing this code you agree with the License terms and conditions.
# * You can obtain License text at https://github.com/retentioneering/retentioneering-tools/blob/master/LICENSE.md

import pandas as pd


def get_graph_nodelist(self, cols=None):
    event_col = self.retention_config['event_col']
    time_col = self.retention_config['event_time_col']
    # old = self._obj[event_col].value_counts()

    res = self._obj.groupby([event_col])[time_col].count().reset_index()
    
    if cols is not None:
        for weight_col in cols:
            by_col = self._obj.groupby([event_col])[weight_col].nunique().reset_index()
            res = res.join(by_col[weight_col])

    res = res.sort_values(by=time_col, ascending=False)
    res.rename(columns={time_col: "number_of_events"}, inplace=True)

    return res 

