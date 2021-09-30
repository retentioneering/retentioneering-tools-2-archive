# * Copyright (C) 2020 Maxim Godzi, Anatoly Zaytsev, Retentioneering Team
# * This Source Code Form is subject to the terms of the Retentioneering Software Non-Exclusive License (License)
# * By using, sharing or editing this code you agree with the License terms and conditions.
# * You can obtain License text at https://github.com/retentioneering/retentioneering-tools/blob/master/LICENSE.md


from typing import Sequence, Mapping, Callable, Type, Optional, Union, MutableMapping, MutableSequence, cast
from typing_extensions import Literal, TypedDict
from pandas import DataFrame
from pandas.core.series import Series


class ReteConfig(TypedDict):
    event_col: str
    event_time_col: str
    user_col: str
    custom_cols: Optional[MutableSequence[str]]
    nodelist_base_col: Optional[str]
    edgelist_base_col: Optional[str]
    experiments_folder: str


NormFunc = Callable[[
    ReteConfig, DataFrame, DataFrame, DataFrame], Series]

NormType = Literal["full", "node"]


class ReteExplorer():
    config: ReteConfig
    clickstream: DataFrame
    nodelist: DataFrame
    edgelist: DataFrame

    edgelist_norm_functions: MutableMapping[str, NormFunc]

    def __init__(
            self,
            clickstream: DataFrame,
            config: ReteConfig
    ):
        self.clickstream = clickstream
        self.config = config
        self.edgelist_norm_functions = {}

    def _get_shift(self, clickstream: DataFrame = None):
        index_col = self.config['user_col']
        event_col = self.config['event_col']
        time_col = self.config['event_time_col']

        data = clickstream.copy() if clickstream is not None else self.clickstream.copy()
        data.sort_values([index_col, time_col], inplace=True)
        shift = data.groupby(index_col).shift(-1)

        data['next_' + event_col] = shift[event_col]
        data['next_' + str(time_col)] = shift[time_col]

        return data

    def get_nodelist_default_col(self):
        d = self.config["nodelist_base_col"] if "nodelist_base_col" in self.config else None
        return d if d is not None else "number_of_events"

    def get_edgelist_default_col(self):
        d = self.config["edgelist_base_col"] if "edgelist_base_col" in self.config is not None else "edge_weight"
        return d if d is not None else "edge_weight"

    def get_custom_cols(self):
        config_custom_cols = self.config["custom_cols"] if "custom_cols" in self.config else [
        ]
        custom_cols = config_custom_cols if config_custom_cols is not None else []
        return custom_cols

    def get_nodelist_cols(self):
        default_col = self.get_nodelist_default_col()
        custom_cols = self.get_custom_cols()
        return list([default_col]) + list(custom_cols)

    def use_edgelist_norm_func(self, col: str, normfunc: NormFunc):
        self.edgelist_norm_functions[col] = normfunc

    def create_nodelist(self, clickstream: DataFrame = None):
        event_col = self.config['event_col']
        time_col = self.config['event_time_col']
        nodelist_default_col = self.get_nodelist_default_col()

        data = clickstream.copy() if clickstream is not None else self.clickstream.copy()
        res = data.groupby([event_col])[time_col].count().reset_index()

        if self.config["custom_cols"] is not None:
            for weight_col in self.config["custom_cols"]:
                by_col = data.groupby([event_col])[
                    weight_col].nunique().reset_index()
                res = res.join(by_col[weight_col])

        res = res.sort_values(by=time_col, ascending=False)
        res.rename(
            columns={time_col: nodelist_default_col}, inplace=True)

        res["active"] = True
        res["alias"] = False
        res["parent"] = None
        res["changed_name"] = None
        return res

    def create_edgelist(self, norm_type: NormType = None, clickstream: DataFrame = None):
        if norm_type not in [None, 'full', 'node']:
            raise ValueError(f'unknown normalization type: {norm_type}')

        event_col = self.config['event_col']
        time_col = self.config['event_time_col']

        cols = [event_col, 'next_' + str(event_col)]
        data = self._get_shift(clickstream)

        default_weight_col = self.get_edgelist_default_col()

        agg = (data
               .groupby(cols)[time_col]
               .count()
               .reset_index())
        agg.rename(columns={time_col: default_weight_col}, inplace=True)

        if self.config["custom_cols"] is not None:
            for weight_col in self.config["custom_cols"]:
                agg_i = (data
                         .groupby(cols)[weight_col]
                         .nunique()
                         .reset_index())
                agg = agg.join(agg_i[weight_col])

        # apply default norm func
        if norm_type == 'full':
            agg[default_weight_col] /= agg[default_weight_col].sum()
            if self.config["custom_cols"] is not None:
                for weight_col in self.config["custom_cols"]:
                    agg[weight_col] /= data[weight_col].nunique()

        if norm_type == 'node':
            event_transitions_counter = data.groupby(
                event_col)[cols[1]].count().to_dict()

            s = agg[default_weight_col]
            agg[default_weight_col] /= agg[cols[0]
                                           ].map(event_transitions_counter)

            if self.config["custom_cols"] is not None:
                for weight_col in self.config["custom_cols"]:
                    user_counter = data.groupby(
                        cols[0])[weight_col].nunique().to_dict()
                    agg[weight_col] /= agg[cols[0]].map(user_counter)

        # TODO: подумать над этим
        # apply custom norm func for event col
        if default_weight_col in self.edgelist_norm_functions:
            agg[default_weight_col] = self.edgelist_norm_functions[default_weight_col](
                self.config, data, self.nodelist, agg)

        if self.config["custom_cols"] is not None:
            for weight_col in self.config["custom_cols"]:
                if weight_col in self.edgelist_norm_functions:
                    agg[weight_col] = self.edgelist_norm_functions[weight_col](
                        self.config, data, self.nodelist, agg)

        return agg

    def create_graph(self, norm_type: NormType = None, nodelist: DataFrame = None, edgelist: DataFrame = None):
        from retentioneering.core.rete_graph.rete_graph import ReteGraph

        return ReteGraph(self,
                         clickstream=self.clickstream,
                         nodelist=nodelist if nodelist is not None else self.create_nodelist(),
                         edgelist=edgelist if edgelist is not None else self.create_edgelist(
                             norm_type)
                         )
