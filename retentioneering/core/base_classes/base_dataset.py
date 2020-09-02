import pandas as pd
import numpy as np
import matplotlib as plt
from datetime import timedelta
from retentioneering.core import feature_extraction
from retentioneering.core import clustering
from retentioneering.visualization import plot, funnel
from sklearn.linear_model import LogisticRegression
from retentioneering.core.model import ModelDescriptor
from retentioneering.core import preprocessing
from sklearn.feature_extraction.text import CountVectorizer

from .base_trajectory import BaseTrajectory


class BaseDataset(BaseTrajectory):

    def __init__(self, pandas_obj):
        super(BaseDataset, self).__init__(pandas_obj)
        self._embedding_types = ['tfidf', 'counts', 'frequency']
        self._locals = None

    def _init_cols(self, caller_locals):
        if caller_locals:
            self._locals = caller_locals
        return

    def _event_col(self):
        col_name = 'event_col'
        col = None
        if self._locals:
            col = self._locals.get(col_name)
            if col is None:
                kwargs = self._locals.get('kwargs')
                if kwargs:
                    col = kwargs.get(col_name)
        return self.retention_config[col_name] if col is None else col

    def _index_col(self):
        col_name = 'index_col'
        col = None
        if self._locals:
            col = self._locals.get(col_name)
            if col is None:
                kwargs = self._locals.get('kwargs')
                if kwargs:
                    col = kwargs.get(col_name)
        return self.retention_config[col_name] if col is None else col

    def _event_time_col(self):
        col_name = 'time_col'
        col = None
        if self._locals:
            col = self._locals.get(col_name)
            if col is None:
                kwargs = self._locals.get('kwargs')
                if kwargs:
                    col = kwargs.get(col_name)
        return self.retention_config['event_time_col'] if col is None else col

    def prepare_vocab(self, ngram_range=(1, 2), min_threshold=0, min_coeff=0, exclude_cycles=False,
                      exclude_loops=False, exclude_repetitions=False):
        """

        Parameters
        ----------
        ngram_range - set of two numbers for ngram range
        min_threshold - lower bound of occurences number for ngram to pass
        min_coeff - lower bound of how much the coefficient is far away from 1 for ngram to pass
        exclude_cycles - should the cycles be excluded?
        exclude_loops - should the loops be excluded?
        exclude_repetitions - should the repetitions in ngrams be excluded? (main catalog catalog cart --> main catalog cart)

        Returns dict with such sequences
        -------

        """
        index_col = self._index_col()
        event_col = self._event_col()
        if min_threshold < 0 or min_coeff < 0:
            raise ValueError("Threshold and coefficient shouldn't be negative!")
        sequences = self.find_sequences(ngram_range=ngram_range, fraction=1, exclude_cycles=exclude_cycles,
                                        exclude_loops=exclude_loops, exclude_repetitions=exclude_repetitions)
        sequences = sequences[
            ((sequences.Lost + sequences.Good) >= min_threshold) & (abs(sequences.Lost2Good - 1) >= min_coeff)]
        vocab = {' '.join(ngram.lower().split('~~')): ind for ind, ngram in enumerate(sequences.Sequence)}
        return vocab

    def extract_features(self, feature_type='tfidf', drop_targets=True, metadata=None, **kwargs):
        """
        User trajectories vectorizer.

        Parameters
        --------
        feature_type: str, optional
            Type of vectorizer. Available vectorization methods:
            - TFIDF (``feature_type='tfidf'``). For more information refer to ``retentioneering.core.feature_extraction.tfidf_embedder``.
            - Event frequencies (``feature_type='frequency'``). For more information refer to ``retentioneering.core.feature_extraction.frequency_embedder``.
            - Event counts (``feature_type='counts'``). For more information refer to ``counts_embedder``.
            Default: ``tfidf``
        drop_targets: bool, optional
            If ``True``, then targets will be removed from feature generation. Default: ``True``
        metadata: pd.DataFrame, optional
            Dataframe with user or session properties or any other information you would like to extract as features (e.g. user properties, LTV values, etc.). Default: ``None``
        meta_index_col: str, optional
            Used when metadata is not ``None``. Name of column in ``metadata`` dataframe that contains the same ID as in ``index_col``, or if not defined, same as in retention_config (e.g ID of users or sessions). If ``None``, then index of metadata dataframe is used instead. Default: ``None``
        manifold_type: str, optional
            Name dimensionality reduction method from ``sklearn.decomposition`` and ``sklearn.manifold``. Default: ``None``
        fillna: optional
            Value for filling missing metadata for any ``index_col`` value. Default: ``None``
        drop: bool, optional
            If ``True``, then drops users which do not exist in ``metadata`` dataframe. Default: ``False``
        ngram_range: tuple, optional
            Range of ngrams to use in feature extraction. Default: ``(1, 1)``
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.
        event_col: str, optional
            Name of custom event column, for more information refer to ``init_config``. For instance, you may want to aggregate some events or rename and use it as new event column. By default the column defined in ``init_config`` will be used as ``event_col``.
        vocab_pars: dict, optional
            dictionary of parameters for creating vocabulary of ngrams with prepare_vocab() function. This vocab will be used as a feature space for TF-EDF encoding

        kwargs: optional
            Keyword arguments for ``sklearn.decomposition`` and ``sklearn.manifold`` methods.

        Returns
        -------
        Encoded user trajectories

        Return type
        -------
        pd.DataFrame of (number of users, number of unique events | event n-grams)
        """
        self._init_cols(locals())
        if feature_type not in self._embedding_types:
            raise ValueError("Unknown feature type: {}.\nPlease choose one from {}".format(
                feature_type,
                ' '.join(self._embedding_types)
            ))

        func = getattr(feature_extraction, feature_type + '_embedder')
        if drop_targets:
            tmp = self._obj[
                ~self._obj[self._event_col()].isin(self.retention_config['target_event_list'])
            ].copy()
        else:
            tmp = self._obj
        vocab = None

        if 'vocab_pars' in kwargs.keys():
            vocab = self.prepare_vocab(**kwargs['vocab_pars'])
            if 'ngram_range' not in kwargs['vocab_pars'].keys():
                ngram_range = (1,1)
                kwargs['ngram_range']=ngram_range
                vocab = self.prepare_vocab(**kwargs['vocab_pars'])
        res = func(tmp, vocab=vocab, **kwargs)
        if metadata is not None:
            res = feature_extraction.merge_features(res, metadata, **kwargs)
        return res

    def extract_features_from_test(self, test, train=None, **kwargs):
        """
        Extracts features from test dataset

        Parameters
        -------
        test: pd.DataFrame
            Test subsample of clickstream
        train: pd.DataFrame, optional
            Train subsample of clickstream
        kwargs:
            ``BaseDataset.rete.extract_features()`` parameters.

        Returns
        -------
        Encoded user trajectories.

        Return type
        -------
        pd.DataFrame of (number of users in test, number of unique events | event n-grams in train)
        """
        if train is None:
            train = self.extract_features(**kwargs)
        test = test.rete.extract_features(**kwargs)
        test = test.loc[:, train.columns.tolist()]
        return test.fillna(0)

    def _make_target(self):
        self._init_cols(locals())
        target = (self._obj
                  .groupby(self._index_col())
                  .apply(lambda x: self.retention_config['positive_target_event'] in x[self._event_col()]))
        return target

    def get_clusters(self, plot_type=None, refit_cluster=False, method='simple_cluster', **kwargs):
        """
        Finds clusters of users in data.

        Parameters
        --------
        plot_type: str, optional
            Type of clustering visualization. Available methods are ``cluster_heatmap``, ``cluster_tsne``, ``cluster_pie``, ``cluster_bar``. Please, see examples to understand different visualization methods. Default: ``None``
        refit_cluster: bool, optional
            If ``False``, then cached results of clustering are used. Default: ``False``
        method: str, optional
            Method of clustering. Available methods:
                - ``simple_cluster``;
                - ``dbscan``;
                - ``GMM``.
            Default: ``simple_cluster``
        use_csi: bool, optional
            If ``True``, then cluster stability index will be calculated. IMPORTANT: it may take a lot of time. Default: ``True``
        epsq: float, optional
            Quantile of nearest neighbor positive distance between dots, its value will be an eps. If ``None``, then eps from keywords will be used. Default: ``None``
        max_cl_number: int, optional
            Maximal number of clusters for aggregation of small clusters. Default: ``None``
        max_n_clusters: int, optional
            Maximal number of clusters for automatic selection for number of clusters. If ``None``, then uses n_clusters from arguments. Default: `None```
        random_state: int, optional
            Random state for KMeans and GMM clusterers.
        feature_type: str, optional
            Type of vectorizer. Available vectorization methods:
            - TFIDF (``feature_type='tfidf'``). For more information refer to ``retentioneering.core.feature_extraction.tfidf_embedder``.
            - Event frequencies (``feature_type='frequency'``). For more information refer to ``retentioneering.core.feature_extraction.frequency_embedder``.
            - Event counts (``feature_type='counts'``). For more information refer to ``counts_embedder``.
            Default: ``tfidf``
        drop_targets: bool, optional
            If ``True``, then targets will be removed from feature generation. Default: ``True``
        metadata: pd.DataFrame, optional
            Dataframe with user or session properties or any other information you would like to extract as features (e.g. user properties, LTV values, etc.). Default: ``None``
        meta_index_col: str, optional
            Used when metadata is not ``None``. Name of column in ``metadata`` dataframe that contains the same ID as in ``index_col``, or if not defined, same as in retention_config (e.g ID of users or sessions). If ``None``, then index of metadata dataframe is used instead. Default: ``None``
        manifold_type: str, optional
            Name dimensionality reduction method from ``sklearn.decomposition`` and ``sklearn.manifold``. Default: ``None``
        fillna: optional
            Value for filling missing metadata for any ``index_col`` value. Default: ``None``
        drop: bool, optional
            If ``True``, then drops users which do not exist in ``metadata`` dataframe. Default: ``False``
        ngram_range: tuple, optional
            Range of ngrams to use in feature extraction. Default: ``(1, 1)``
        index_col:
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.
        event_col:
            Name of custom event column, for more information refer to ``init_config``. For instance, you may want to aggregate some events or rename and use it as new event column. By default the column defined in ``init_config`` will be used as ``event_col``.
        kwargs:
            Parameters for ``sklearn.decomposition()`` and ``sklearn.manifold()`` methods. Keyword arguments for clusterers. For more information, please, see ``sklearn.cluster.KMeans()``, ``sklearn.cluster.DBSCAN()``, ``sklearn.mixture.GaussianMixture()`` docs.

        Returns
        -------
        Array of clusters

        Return type
        -------
        np.array
        """
        if hasattr(self, 'datatype') and self.datatype == 'features':
            features = self._obj.copy()
        else:
            features = self.extract_features(**kwargs)
        if not hasattr(self, 'clusters') or refit_cluster:
            clusterer = getattr(clustering, method)
            self.clusters, self._metrics = clusterer(features, **kwargs)
            self._create_cluster_mapping(features.index.values)

        if hasattr(self, 'datatype') and self.datatype == 'features':
            target = kwargs.pop('target')
        else:
            target = self.get_positive_users(**kwargs)
        target = features.index.isin(target)
        self._metrics['homogen'] = clustering.homogeneity_score(target, self.clusters)
        if hasattr(self, '_tsne'):
            features.rete._tsne = self._tsne
        if plot_type:
            func = getattr(plot, plot_type)
            res = func(
                features,
                clustering.aggregate_cl(self.clusters, 7) if method == 'dbscan' else self.clusters,
                target, refit = refit_cluster,
                metrics=self._metrics,
                **kwargs
            )
            if res is not None:
                self._tsne = res
        return self.clusters

    def _create_cluster_mapping(self, ids):
        self.cluster_mapping = {}
        for cluster in set(self.clusters):
            self.cluster_mapping[cluster] = ids[self.clusters == cluster].tolist()

    def filter_cluster(self, cluster_name, index_col=None):
        """
        Filters dataset against one or several clusters.

        Parameters
        --------
        cluster_name: int or list
            Cluster ID or list of cluster IDs for filtering.
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. If ``None``, the column defined in ``init_config`` will be used as ``index_col``. Default: ``None``

        Returns
        --------
        Filtered dataset

        Return type
        --------
        pd.Dataframe
        """
        self._init_cols(locals())
        ids = []
        if type(cluster_name) is list:
            for i in cluster_name:
                ids.extend(self.cluster_mapping[i])
        else:
            ids = self.cluster_mapping[cluster_name]
        return self._obj[self._obj[self._index_col()].isin(ids)].copy().reset_index(drop=True)

    def cluster_funnel(self, cluster, funnel_events, index_col=None, event_col=None,
                       user_based=True, interactive=True, **kwargs):
        """
        Plots funnel over given event list as number of users who pass through each event

        Parameters
        --------
        cluster: int or list
            Cluster ID or list of cluster IDs to create a funnel for.
        funnel_events: list
            List of event in funnel. Visualization order will be the same as in list.
        user_based: bool, optional
            If ``True``, then edge weights is calculated as unique rate of users who go through them, else as event count. Default: ``True``
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.
        event_col: str, optional
            Name of custom event column, for more information refer to ``init_config``. For instance, you may want to aggregate some events or rename and use it as new event column. By default the column defined in ``init_config`` will be used as ``event_col``.

        Returns
        --------
        Funnel visualisation

        Return type
        --------
        Plotly
        """
        self._init_cols(locals())
        if user_based:
            counts = self.filter_cluster(
                cluster, index_col=self._index_col()
            ).groupby(self._event_col())[self._index_col()].nunique().loc[funnel_events]
        else:
            counts = self.filter_cluster(
                cluster, index_col=index_col
            ).groupby(self._event_col())[self._event_time_col()].count().loc[funnel_events]
        counts = counts.fillna(0)
        return funnel.funnel_chart(counts.astype(int).tolist(),
                                   funnel_events,
                                   'Funnel for cluster {}'.format(cluster),
                                   interactive=interactive)

    def cluster_top_events(self, n=3):
        """
        Shows most frequent ``event_col`` values for each cluster along with count and frequency of such events.

        Parameters
        ----------
        n: int, optional
            Number of most frequent events. Default: ``3``

        Returns
        -------
        Prints events statistics for each cluster in output.
        """
        self._init_cols(locals())
        if not hasattr(self, 'clusters'):
            raise ValueError('Please build clusters first')
        if not hasattr(self, '_inv_cl_map'):
            self._inv_cl_map = {k: i for i, j in self.cluster_mapping.items() for k in j}
        cl = self._obj[self._index_col()].map(self._inv_cl_map).rename('cluster')
        topn = self._obj.groupby([cl, self._event_col()]).size().sort_values(
            ascending=False).reset_index()
        tot = topn.groupby(['cluster'])[0].sum()
        topn = topn.join(tot, on='cluster', rsuffix='_tot')
        topn['freq'] = (topn['0'] / topn['0_tot'] * 100).round(2).astype(str) + '%'
        for i in set(topn.cluster):
            print(f'Cluster {i}:')
            print(topn[topn.cluster == i].iloc[:n, [1, 2, 4]].rename({
                '0': 'count'
            }, axis=1))

    def cluster_event_dist(self, cl1, cl2=None, n=3, event_col=None, index_col=None, **kwargs):
        """
        Plots frequency of top events in cluster ``cl1`` in comparison with frequency of such events in whole data or in cluster ``cl2``.

        Parameters
        ---------
        cl1: int
            ID of the first cluster to search top events from it.
        cl2: int, optional
            ID of the second cluster to compare with top events from first cluster. If ``None``, then compares with all data. Default: ``None``
        n: int, optional
            Number of top events. Default: ``3``
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.
        event_col: str, optional
            Name of custom event column, for more information refer to ``init_config``. For instance, you may want to aggregate some events or rename and use it as new event column. By default the column defined in ``init_config`` will be used as ``event_col``.

        Returns
        ---------
        Plots distribution barchart
        """
        self._init_cols(locals())
        clus = self.filter_cluster(cl1, index_col=index_col)
        top_cluster = (clus
                       [self._event_col()]
                       .value_counts().head(n) / clus.shape[0]).reset_index()
        cr0 = (
            clus[
                clus[self._event_col()] == self.retention_config['positive_target_event']
            ][self._index_col()].nunique()
        ) / clus[self._index_col()].nunique()
        if cl2 is None:
            clus2 = self._obj
        else:
            clus2 = self.filter_cluster(cl2, index_col=index_col)
        top_all = (clus2
                   [self._event_col()]
                   .value_counts()
                   .loc[top_cluster['index']]
                   / clus2.shape[0]).reset_index()
        cr1 = (
            clus2[
                clus2[self._event_col()] == self.retention_config['positive_target_event']
            ][self._index_col()].nunique()
        ) / clus2[self._index_col()].nunique()
        top_all.columns = [self._event_col(), 'freq', ]
        top_cluster.columns = [self._event_col(), 'freq', ]

        top_all['hue'] = 'all' if cl2 is None else f'cluster {cl2}'
        top_cluster['hue'] = f'cluster {cl1}'

        plot.cluster_event_dist(
            top_all.append(top_cluster, ignore_index=True, sort=False),
            self._event_col(),
            cl1,
            [
                clus[self._index_col()].nunique() / self._obj[self._index_col()].nunique(),
                clus2[self._index_col()].nunique() / self._obj[self._index_col()].nunique(),
             ],
            [cr0, cr1],
            cl2
        )

    def create_model(self, model_type=LogisticRegression, regression_targets=None, **kwargs):
        """
        Creates model explainer for a given model.

        Parameters
        --------
        model_type: sklearn class
            Model class in sklearn-api style (should have methods `fit`, `predict_proba`).
        regression_targets: dict, optional
            Mapping from ``index_col`` to regression target e.g. LTV of user. Default: ``None``
        kwargs:
            Parameters for model class that you use, also contains parameters for ``retention.extract_features()``.

        Returns
        --------
        Creates ModelDescriptor
        """
        if hasattr(self, 'datatype') and self.datatype == 'features':
            features = self._obj.copy()
        else:
            if 'ngram_range' not in kwargs:
                kwargs.update({'ngram_range': (1, 2)})
            features = self.extract_features(**kwargs)
        if regression_targets is not None:
            target = self.make_regression_targets(features, regression_targets)
        else:
            target = features.index.isin(self.get_positive_users(**kwargs))
        feature_range = kwargs.pop('ngram_range')
        mod = ModelDescriptor(model_type, features, target, feature_range=feature_range, **kwargs)
        return mod

    @staticmethod
    def make_regression_targets(features, regression_targets):
        """
        Creates target vector for given features.

        Parameters
        --------
        features: pd.DataFrame
            Feature matrix.
        regression_targets: dict
            Mapping from ``index_col`` to regression target, e.g. LTV of user.

        Returns
        --------
        List of targets alligned to feature matrix indices

        Return type
        -------

        """
        return [regression_targets.get(i) for i in features.index]

    def get_step_matrix_difference(self, groups, plot_type=True, max_steps=30, sorting=True, **kwargs):
        """
        Plots heatmap similar to ``get_step_matrix()`` matrix but with difference of events distributions over steps between two given groups.

        Parameters
        --------
        groups: boolean pd.Series
            Boolean vector that splits data into groups. For more information refer to ``create_filter()`` method.
        max_steps: int, optional
            Maximum number of steps in trajectory to include. Depending on ``reverse`` parameter value, the steps are counted from the beginning of trajectories if ``reverse=False``, or from the end otherwise.
        plot_type: bool, optional
            If ``True``, then plots step matrix in interactive session (Jupyter notebook). Default: ``True``
        thr: float, optional
            Used to prune matrix and display only the rows with at least one value >= ``thr``. Default: ``None``
        reverse: str or list, optional
            This parameter is used to display reversed matrix from target events towards the beginning of trajectories.
            Range of possible values:
                - ``None``: displays default step matrix from the start of trajectories. Uses all the user trajectories.
                - ``'pos'``: displays reverse step matrix in such a way that the first column is the ``positive_target_event`` share, which is always 1, and the following columns reflect the share of users on final steps before reaching the target. Uses only those trajectories, which ended up having at least one ``positive_target_event`` in trajectory.
                - ``'neg'``: same as ``pos`` but for ``negative_target_event``. Uses only those trajectories, which ended up having at least one ``negative_target_event`` in trajectory.
                - ``['pos', 'neg']``: combination of ``pos`` and ``neg`` options, first column has only target events. Uses all the trajectories with target events inside.
            Default: ``None``
        sorting: bool, optional
            If ``True``, then automatically places elements with highest values in top. Rows are sorted in such a way that the first one has highest first column value, second row has the highest second column value,besides already used first value, etc. With this sorting you may see a dominant trajectory as a diagonal. Default: ``True``
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.
        event_col: str, optional
            Name of custom event column, for more information refer to ``init_config``. For instance, you may want to aggregate some events or rename and use it as new event column. By default the column defined in ``init_config`` will be used as ``event_col``.
        cols: list or str
            List of source and target columns, e.g. ``event_name`` and ``next_event``. ``next_event`` column is created automatically during ``BaseTrajectory.rete.prepare()`` method execution. Default: ``None`` wich corresponds to ``event_col`` value from ``retention_config`` and 'next_event'.
        weight_col: str, optional
            Aggregation column for edge weighting. For instance, you may set it to the same value as in ``index_col`` and define ``edge_attributes='users_unique'`` to calculate unique users passed through edge. Default: ``None``
        edge_attributes: str, optional
            Edge weighting function and the name of field is defined with this parameter. It is set with two parts and a dash inbetween: ``[this_column_name]_[aggregation_function]``. The first part is the custom name of this field. The second part after `_` should be a valid ``pandas.groupby.agg()`` parameter, e.g. ``count``, ``sum``, ``nunique``, etc. Default: ``event_count``.
        dt_means: bool, optional
            If ``True``, adds mean time between events to step matrix. Default: ``False``
        title: str, optional
            Title for step matrix plot.

        Returns
        -------
        Dataframe with ``max_steps`` number of columns and len(event_col.unique) number of rows at max, or less if used ``thr`` > 0.

        Return type
        -------
        pd.DataFrame
        """
        reverse = None
        thr_value = kwargs.pop('thr', None)
        if groups.mean() == 1:
            diff = self._obj[groups].copy().trajectory.get_step_matrix(plot_type=False, max_steps=max_steps, **kwargs)
        elif groups.mean() == 0:
            diff = -self._obj[~groups].copy().trajectory.get_step_matrix(plot_type=False, max_steps=max_steps, **kwargs)
        else:
            reverse = kwargs.pop('reverse', None)
            if type(reverse) is list:
                desc_old = self._obj[~groups].copy().trajectory.get_step_matrix(plot_type=False,
                                                                                max_steps=max_steps, reverse='neg',
                                                                                for_diff=True,
                                                                                **kwargs)
                desc_new = self._obj[groups].copy().trajectory.get_step_matrix(plot_type=False,
                                                                               max_steps=max_steps,
                                                                               for_diff=True,
                                                                               reverse='pos', **kwargs)
            else:
                desc_old = self._obj[~groups].copy().trajectory.get_step_matrix(plot_type=False,
                                                                                max_steps=max_steps,
                                                                                for_diff=True,
                                                                                reverse=reverse, **kwargs)
                desc_new = self._obj[groups].copy().trajectory.get_step_matrix(plot_type=False,
                                                                               max_steps=max_steps,
                                                                               for_diff=True,
                                                                               reverse=reverse, **kwargs)
            desc_old, desc_new = self._create_diff_index(desc_old, desc_new)
            desc_old, desc_new = self._diff_step_allign(desc_old, desc_new)
            diff = desc_new - desc_old
        if thr_value:
            diff = self._process_thr(diff, thr_value, max_steps, mod=abs, **kwargs)
        diff = diff.sort_index(axis=1)
        if kwargs.get('reverse'):
            diff.columns = ['n'] + ['n - {}'.format(i - 1) for i in diff.columns[1:]]
        if sorting:
            diff = self._sort_matrix(diff)
        if plot_type:
            plot.step_matrix(
                diff.round(2),
                title=kwargs.get('title',
                                 'Step matrix ({}) difference between positive and negative class ({} - {})'.format(
                                     'reversed' if reverse else '',
                                     self.retention_config['positive_target_event'],
                                     self.retention_config['negative_target_event'],
                                 )), **kwargs)
        return diff

    def _process_target_config(self, data, cfg, target):
        target = 'positive_target_event' if target.startswith('pos_') else 'negative_target_event'
        target = self.retention_config.get(target)
        for key, val in cfg.items():
            func = getattr(self, f'_process_{key}')
            data = func(data, val, target)
        return data

    def _process_time_limit(self, data, threshold, name):
        self._init_cols(locals())
        if 'next_timestamp' in data:
            col = 'next_timestamp'
            change_next = True
            data[self._event_time_col()] \
                = pd.to_datetime(data[self._event_time_col()])
        else:
            col = self._event_time_col()
            change_next = False
        data[col] = pd.to_datetime(data[col])
        max_time = data[col].max()
        tmp = data.groupby(self._index_col()).tail(1)
        tmp = tmp[(max_time - tmp[col]).dt.total_seconds() > threshold]

        if change_next:
            tmp[self._event_col()] = tmp.next_event.values
            tmp.next_event = name
            tmp[self._event_time_col()] += timedelta(seconds=1)
            tmp['next_timestamp'] += timedelta(seconds=1)
        else:
            tmp[self._event_col()] = name
            tmp[self._event_time_col()] += timedelta(seconds=1)
        data.reset_index(drop=True, inplace=True)

        return data.append(tmp, ignore_index=True).reset_index(drop=True)

    def _process_event_list(self, data, event_list, name):
        self._init_cols(locals())
        if 'next_event' in data:
            col = 'next_event'
        else:
            col = self._event_col()
        data[col] = np.where(data[col].isin(event_list), name, data[col])
        return data

    def _process_empty(self, data, other, name):
        self._init_cols(locals())
        if 'next_event' in data:
            col = 'next_event'
            change_next = True
            data['next_timestamp'] \
                = pd.to_datetime(data[self._event_time_col()])
        else:
            col = self._event_col()
            change_next = False
        data[self._event_time_col()] \
            = pd.to_datetime(data[self._event_time_col()])
        bads = set(data[data[col] == other][self._index_col()])
        goods = set(data[self._index_col()]) - bads
        tmp = data[data[self._index_col()].isin(goods)]
        tmp = tmp.groupby(self._index_col()).tail(1)
        if change_next:
            tmp[self._event_col()] = tmp.next_event.values
            tmp.next_event = name
            tmp[self._event_time_col()] += timedelta(seconds=1)
            tmp['next_timestamp'] += timedelta(seconds=1)
        else:
            tmp[self._event_col()] = name
            tmp[self._event_time_col()] += timedelta(seconds=1)
        data.reset_index(drop=True, inplace=True)
        return data.append(tmp, ignore_index=True).reset_index(drop=True)

    def _add_first_event(self, first_event):
        self._init_cols(locals())
        top1 = self._obj.groupby(self._index_col()).head(1)
        if 'next_event' in top1:
            top1.next_event = top1[self._event_col()].values
        top1[self._event_col()] = first_event
        top1[self._event_time_col()] -= timedelta(seconds=1)
        return top1.append(self._obj, ignore_index=True).reset_index(drop=True)

    def _convert_timestamp(self, time_col=None):
        self._init_cols(locals())
        timestamp = self._obj[self._event_time_col()].iloc[0]
        if hasattr(timestamp, 'second'):
            return
        if type(timestamp) != str:
            l = len(str(int(timestamp)))
            self._obj[self._event_time_col()] *= 10 ** (19 - l)
        self._obj[self._event_time_col()] = pd.to_datetime(self._obj[self._event_time_col()])

    def prepare(self, first_event=None):
        """
        Populates dataset with target events based on target event description in ``retention_config``.

        Parameters
        --------
        first_event: str, optional
            If not ``None``, then adds ``first_event`` for each ``index_col`` as a fist event in trajectory. Default: ``None``

        Returns
        --------
        Populates dataset with target events.
        """
        self._init_cols(locals())
        self._convert_timestamp()
        self._obj.sort_values(self._event_time_col(), inplace=True)
        if hasattr(self._obj, 'next_timestamp'):
            self._convert_timestamp('next_timestamp')
        if first_event is not None:
            data = self._add_first_event(first_event)
        else:
            data = self._obj.copy()
        prev_shape = data.shape[0]
        data = data[data[self.retention_config.get('event_col')].notnull()]
        data = data[data[self.retention_config.get('index_col')].notnull()]
        if data.shape[0] - prev_shape:
            print("There is null {} or {} in your data.\nDataset is filtered for {} of missed data.".format(
                self.retention_config.get('event_col'),
                self.retention_config.get('index_col'),
                data.shape[0] - prev_shape
            ))
        targets = {
            'pos_target_definition',
            'neg_target_definition'
        }
        if (self.retention_config.get('positive_target_event') in set(self._obj[self.retention_config.get('event_col')])
                or self.retention_config.get('pos_target_definition') is None):
            targets = targets - {'pos_target_definition'}
        if (self.retention_config.get('negative_target_event') in set(self._obj[self.retention_config.get('event_col')])
                or self.retention_config.get('neg_target_definition') is None):
            targets = targets - {'neg_target_definition'}
        empty_definition = []
        for target in targets:
            tmp = self.retention_config.get(target)
            if len(tmp) == 0:
                empty_definition.append(target)
                continue
            data = self._process_target_config(data, tmp, target)

        if len(empty_definition) == 2:
            return data
        for target in empty_definition:
            other = (self.retention_config['positive_target_event']
                     if target.startswith('neg_')
                     else self.retention_config['negative_target_event'])
            target = (self.retention_config['positive_target_event']
                      if target.startswith('pos_')
                      else self.retention_config['negative_target_event'])
            data = self._process_empty(data, other, target)

        return data

    def get_positive_users(self, index_col=None, **kwargs):
        """
        Returns users who have ``positive_target_event`` in their trajectories.

        Parameters
        --------
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.

        Returns
        --------
        Array of users with ``positive_target_event`` in trajectory.

        Return type
        -------
        np.array
        """
        self._init_cols(locals())
        pos_users = (
            self._obj[self._obj[self._event_col()] == self.retention_config['positive_target_event']][self._index_col()].unique()
        )
        return pos_users.tolist()


    def get_negative_users(self, index_col=None, **kwargs):
        """
        Returns users who have ``negative_target_event`` in their trajectories.

        Parameters
        --------
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.

        Returns
        --------
        Array of users with ``negative_target_event`` in trajectory.

        Return type
        -------
        np.array
        """
        self._init_cols(locals())
        good_users = (
            self._obj[self._obj[self._event_col()] == self.retention_config['positive_target_event']][self._index_col()].unique()
        )
        return self._obj[~self._obj[self._index_col()].isin(good_users)][self._index_col()].unique().tolist()
        # return neg_users.tolist()

    def filter_event_window(self, event_name, neighbor_range=3, direction="both",
                            event_col=None, index_col=None, use_padding=True):
        """
        Filters clickstream data for specific event and its neighborhood.

        Parameters
        ---------
        event_name: str
            Event of interest.
        neighbor_range:
            Number of events to the left and right from event of interest. Default: ``3``
        direction:
            If "both" then takes all neighbours of specific event in both sides: before and after
            If "before" then takes events only before specific event
            If "after" then takes events only after specific event
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.
        event_col: str, optional
            Name of custom event column, for more information refer to ``init_config``. For instance, you may want to aggregate some events or rename and use it as new event column. By default the column defined in ``init_config`` will be used as ``event_col``.
        use_padding: bool, optional
            If ``True``, then all tracks are alligned with `sleep` event. After allignment all first `event_name` in a trajectory will be at a point `neighbor_range + 1`

        Returns
        -------
        Filtered dataframe

        Return type
        -------
        pd.DataFrame
        """
        self._init_cols(locals())
        self._obj['flg'] = self._obj[self._event_col()] == event_name
        f = pd.Series([False] * self._obj.shape[0], index=self._obj.index)
        for i in range(-neighbor_range, neighbor_range + 1, 1):
            if (direction == "after") and (i < 0):
                continue
            if (direction == "before") and (i > 0):
                continue
            f |= self._obj.groupby(self._index_col()).flg.shift(i).fillna(False)
        x = self._obj[f].copy()
        if use_padding and (direction != "after"):
            x = self._pad_event_window(x, event_name, neighbor_range, event_col, index_col)
        return x

    def _pad_number(self, x, event_name, neighbor_range, event_col=None):
        self._init_cols(locals())
        minn = x[x[self._event_col()] == event_name].event_rank.min()
        return neighbor_range - minn + 1

    def _pad_time(self, x, event_name, event_col=None):
        self._init_cols(locals())
        minn = (x[x[self._event_col()] == event_name][self._event_time_col()].min())
        return minn - pd.Timedelta(1, 's')

    def _pad_event_window(self, x, event_name, neighbor_range=3, event_col=None, index_col=None):
        self._init_cols(locals())
        x['event_rank'] = 1
        x.event_rank = x.groupby(self._index_col()).event_rank.cumsum()
        res = x.groupby(self._index_col()).apply(self._pad_number,
                                                 event_name=event_name,
                                                 neighbor_range=neighbor_range,
                                                 event_col=self._event_col())
        res = res.map(lambda y: ' '.join(y * ['sleep']))
        res = res.str.split(expand=True).reset_index().melt(self._index_col())
        res = res.drop('variable', 1)
        res = res[res.value.notnull()]
        tm = (x
              .groupby(self._index_col()).apply(self._pad_time,
                                                event_name=event_name,
                                                event_col=self._event_col()))
        res = res.join(tm.rename('time'), on=self._index_col())
        res.columns = [
            self._index_col(),
            self._event_col(),
            self._event_time_col()
        ]
        res = res.reindex(x.columns, axis=1)
        res = res.append(x, ignore_index=True, sort=False)
        return res.reset_index(drop=True)

    def create_filter(self, index_col=None, cluster_list=None, cluster_mapping=None):
        """
        Creates filter for ``get_step_matrix_difference()`` method based on target classes or clusters.

        Parameters
        -------
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.
        cluster_list: list, optional
            List of clusters from which others will be substract. Default: ``None``
        cluster_mapping: str, optional
            Mapping from clusters to list of users. IMPORTANT: if you use cluster subsample of source data, then it will be necessary to set ``cluster_mapping=source_data.rete.cluster_mapping``.

        Returns
        -------
        Boolean array with filter

        Return type
        -------
        Boolean pd.Series
        """
        index_col = index_col or self.retention_config['index_col']

        if cluster_list is None:
            pos_users = self.get_positive_users(index_col)
            return self._obj[index_col].isin(pos_users)
        else:
            ids = []
            for i in cluster_list:
                ids.extend((cluster_mapping or self.cluster_mapping)[i])
            return self._obj[index_col].isin(ids)

    def calculate_delays(self, plotting=True, time_col=None, index_col=None, event_col=None, bins=15, **kwargs):
        """
        Displays the logarithm of delay between ``time_col`` with the next value in nanoseconds as a histogram.

        Parameters
        --------
        plotting: bool, optional
            If ``True``, then histogram is plotted as a graph. Default: ``True``
        time_col: str, optional
            Name of custom time column for more information refer to ``init_config``. For instance, if in config you have defined ``event_time_col`` as ``server_timestamp``, but want to use function over ``user_timestamp``. By default the column defined in ``init_config`` will be used as ``time_col``.
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.
        event_col: str, optional
            Name of custom event column, for more information refer to ``init_config``. For instance, you may want to aggregate some events or rename and use it as new event column. By default the column defined in ``init_config`` will be used as ``event_col``.
        bins: int, optional
            Number of bins for visualisation. Default: ``50``

        Returns
        -------
        Delays in seconds for each ``time_col``. Index is preserved as in original dataset.

        Return type
        -------
        List
        """
        self._init_cols(locals())
        data = self.get_shift(index_col = self._index_col(),
                              event_col = self._event_col()).copy()

        delays = np.log((data['next_timestamp'] - data[self._event_time_col()]) // pd.Timedelta('1s'))

        if plotting:
            fig, ax = plot.sns.mpl.pyplot.subplots(figsize=kwargs.get('figsize', (15, 7)))  # control figsize for proper display on large bin numbers
            _, bins, _ = plt.hist(delays[~np.isnan(delays) & ~np.isinf(delays)], bins=bins, log=True)
            if not kwargs.get('logvals', False):  # test & compare with logarithmic and normal
                plt.xticks(bins, np.around(np.exp(bins), 1))
            plt.show()

        return np.exp(delays)

    def insert_sleep_events(self, events, delays=None, time_col=None, index_col=None, event_col=None):
        """
        Populates given dataset with sleep events representing time difference between occuring events. Note that this method is not inplace.

        Parameters
        --------
        events: dict
            Event name and log nanosecond ranges in the following structure: ``'event_name' : ['from_logtime', 'to_logtime']``. Keys of the dictionary are custom event names, while values are lists of two floats indicating start and end of time difference in lorarithm nanoseconds.
        delays: list
            Timestamp differences of each event with the next one. If ``None``, then uses ``BaseDataset.rete.calculate_delays()``. Default: ``None``
        time_col: str, optional
            Name of custom time column for more information refer to ``init_config``. For instance, if in config you have defined ``event_time_col`` as ``server_timestamp``, but want to use function over ``user_timestamp``. By default the column defined in ``init_config`` will be used as ``time_col``.
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.
        event_col:  str, optional
            Name of custom event column, for more information refer to ``init_config``. For instance, you may want to aggregate some events or rename and use it as new event column. By default the column defined in ``init_config`` will be used as ``event_col``.

        Returns
        --------
        Original dataframe with inserted sleep events.

        Return type
        -------
        pd.DataFrame
        """

        self._init_cols(locals())

        if delays is None:
            delays = self.calculate_delays(False, self._event_time_col(), self._index_col(), self._event_col())

        data = self._obj.copy()
        to_add = []

        for event_name, (t_min, t_max) in events.items():
            tmp = data.loc[(delays >= t_min) & (delays < t_max)]
            tmp[self._event_col()] = event_name
            tmp[self._event_time_col()] += pd.Timedelta((np.e ** t_min) / 2)
            to_add.append(tmp)
            data['next_event'] = np.where((delays >= t_min) & (delays < t_max), event_name, data['next_event'])
            data['next_timestamp'] = np.where((delays >= t_min) & (delays < t_max),
                                              data[self._event_time_col()] + pd.Timedelta((np.e ** t_min) / 2),
                                              data['next_timestamp'])
        to_add.append(data)
        to_add = pd.concat(to_add)
        return to_add.sort_values(self._event_col()).reset_index(drop=True)

    def remove_events(self, event_list, mode='equal'):
        """
        Removes events from dataset.

        Parameters
        --------
        event_list: list or str
            Events or other elements of ``event_col`` that should be filtered out.
        mode: str, optional
            Type of comparison:
                - `equal`: full event name match with element from ``event_list``;
                - `startswith`: event name starts with element from ``event_list``;
                - `contains`: event name contains element from ``event_list``.

        Returns
        --------
        Filtered dataframe based on event names.

        Return type
        -------
        pd.DataFrame
        """
        self._init_cols(locals())
        data = self._obj.copy()
        func = getattr(preprocessing, '_event_filter_' + mode)

        for event in event_list:
            data = data.loc[func(data[self._event_col()], event)]
        return data.reset_index(drop=True)

    def learn_tsne(self, targets=None, plot_type=None, refit=False, regression_targets=None,
                   sample_size=None, sample_frac=None, proj_type=None, **kwargs):
        """
        <<<REPLACED BY project() function>>>
        <<< NO LONGER SUPPORTED AND WILL BE REMOVED IN THE FUTURE VERSIONS>>

        Learns TSNE projection for selected feature space (`feature_type` in kwargs) and visualizes it with chosen visualization type.

        Parameters
        --------
        targets: np.array, optional
            Vector of targets for users. if None, then calculates automatically based on ``positive_target_event`` and ``negative_target_event``.
        plot_type: str, optional
            Type of projection visualization:
                - ``clusters``: colors trajectories with different colors depending on cluster number.
                - ``targets``: color trajectories based on target reach.
            If ``None``, then only calculates TSNE without visualization. Default: ``None``
        refit: bool, optional
            If ``True``, then TSNE will be refitted, e.g. it is needed if you perform hyperparameters selection.
        regression_targets: dict, optional
            Mapping of ``index_col`` to regression target for custom coloring. For example, if you want to visually evaluate average LTV of user with trajectories clusterization. For more information refer to ``BaseDataset.rete.make_regression_targets()``.
        cmethod: str, optional
            Method of clustering if plot_type = 'clusters'. Refer to ``BaseDataset.rete.get_clusters()`` for more information.
        kwargs: optional
            Parameters for ``BaseDataset.rete.extract_features()``, ``sklearn.manifold.TSNE`` and ``BaseDataset.rete.get_clusters()``

        Returns
        --------
        Dataframe with TSNE transform for user trajectories indexed by user IDs.

        Return type
        --------
        pd.DataFrame
        """
        old_targs = None
        if hasattr(self, 'datatype') and self.datatype == 'features':
            features = self._obj.copy()
        else:
            features = self.extract_features(**kwargs)
            if targets is None:
                if regression_targets is not None:
                    targets = self.make_regression_targets(features, regression_targets)
                else:
                    targets = features.index.isin(self.get_positive_users(**kwargs))
                    targets = np.where(targets, self.retention_config['positive_target_event'],
                                       self.retention_config['negative_target_event'])
            self._tsne_targets = targets

        if sample_frac is not None:
            features = features.sample(frac=sample_frac, random_state=0)
        elif sample_size is not None:
            features = features.sample(n=sample_size, random_state=0)

        if not (hasattr(self, '_tsne') and not refit):
            self._tsne = feature_extraction.learn_tsne(features, **kwargs)
        if plot_type == 'clusters':
            if kwargs.get('cmethod') is not None:
                kwargs['method'] = kwargs.pop('cmethod')
            old_targs = targets.copy()
            targets = self.get_clusters(plot_type=None, **kwargs)
        elif plot_type == 'targets':
            targets = self._tsne_targets
        else:
            return self._tsne
        if proj_type == '3d':
            plot.tsne_3d(
                self._obj,
                clustering.aggregate_cl(targets, 7) if kwargs.get('method') == 'dbscan' else targets,
                old_targs,
                **kwargs
            )
        else:
            plot.cluster_tsne(
                self._obj,
                clustering.aggregate_cl(targets, 7) if kwargs.get('method') == 'dbscan' else targets,
                targets,
                **kwargs
            )
        return self._tsne

    def project(self, method='umap', targets=None, plot_type=None, refit=False, regression_targets=None,
                   sample_size=None, sample_frac=None, proj_type=None, **kwargs):
        """
        Learns manifold projection using selected method for selected feature space (`feature_type` in kwargs) and visualizes it with chosen visualization type.

        Parameters
        --------
        targets: np.array, optional
            Vector of targets for users. if None, then calculates automatically based on ``positive_target_event`` and ``negative_target_event``.
        method: 'umap' or 'tsne'
        plot_type: str, optional
            Type of projection visualization:
                - ``clusters``: colors trajectories with different colors depending on cluster number.
                - ``targets``: color trajectories based on target reach.
            If ``None``, then only calculates TSNE without visualization. Default: ``None``
        refit: bool, optional
            If ``True``, then TSNE will be refitted, e.g. it is needed if you perform hyperparameters selection.
        regression_targets: dict, optional
            Mapping of ``index_col`` to regression target for custom coloring. For example, if you want to visually evaluate average LTV of user with trajectories clusterization. For more information refer to ``BaseDataset.rete.make_regression_targets()``.
        cmethod: str, optional
            Method of clustering if plot_type = 'clusters'. Refer to ``BaseDataset.rete.get_clusters()`` for more information.
        kwargs: optional
            Parameters for ``BaseDataset.rete.extract_features()``, ``sklearn.manifold.TSNE`` and ``BaseDataset.rete.get_clusters()``

        Returns
        --------
        Dataframe with data in the low-dimensional space for user trajectories indexed by user IDs.

        Return type
        --------
        pd.DataFrame
        """
        old_targs = None
        if hasattr(self, 'datatype') and self.datatype == 'features':
            features = self._obj.copy()
        else:
            features = self.extract_features(**kwargs)
            if targets is None:
                if regression_targets is not None:
                    targets = self.make_regression_targets(features, regression_targets)
                else:
                    targets = features.index.isin(self.get_positive_users(**kwargs))
                    targets = np.where(targets, self.retention_config['positive_target_event'],
                                       self.retention_config['negative_target_event'])
            self._tsne_targets = targets

        if sample_frac is not None:
            features = features.sample(frac=sample_frac, random_state=0)
        elif sample_size is not None:
            features = features.sample(n=sample_size, random_state=0)

        if not (hasattr(self, '_tsne') and not refit):
            if method == 'tsne':
                self._tsne = feature_extraction.learn_tsne(features, **kwargs)
            if method == 'umap':
                self._tsne = feature_extraction.learn_umap(features, **kwargs)

        if plot_type == 'clusters':
            if kwargs.get('cmethod') is not None:
                kwargs['method'] = kwargs.pop('cmethod')
            old_targs = targets.copy()
            targets = self.get_clusters(plot_type=None, **kwargs)
        elif plot_type == 'targets':
            targets = self._tsne_targets
        else:
            return self._tsne
        if proj_type == '3d':
            plot.tsne_3d(
                self._obj,
                clustering.aggregate_cl(targets, 7) if kwargs.get('method') == 'dbscan' else targets,
                old_targs,
                **kwargs
            )
        else:
            plot.cluster_tsne(
                self._obj,
                clustering.aggregate_cl(targets, 7) if kwargs.get('method') == 'dbscan' else targets,
                targets,
                **kwargs
            )
        return self._tsne

    def select_bbox_from_tsne(self, bbox, plotting=True, **kwargs):
        """
        Selects data filtered by cordinates of TSNE plot.

        Parameters
        ---------
        bbox: list
            List of lists that contains angles of bbox.
                ```bbox = [
                    [0, 0], # [min x, max x]
                    [10, 10] # [min y, max y]
                ]```
        plotting: bool, optional
            If ``True``, then visualize graph of selected users.

        Returns
        --------
        Dataframe with filtered clickstream of users in bbox.

        Return type
        -------
        pd.DataFrame
        """
        self._init_cols(locals())
        if not hasattr(self, '_tsne'):
            raise ValueError('Please, use `learn_tsne` before selection of specific bbox')

        f = self._tsne.index.values[(self._tsne.iloc[:, 0] >= bbox[0][0])
                                    & (self._tsne.iloc[:, 0] <= bbox[0][1])
                                    & (self._tsne.iloc[:, 1] >= bbox[1][0])
                                    & (self._tsne.iloc[:, 1] <= bbox[1][1])]

        filtered = self._obj[self._obj[self._index_col()].isin(f)]
        if plotting:
            filtered.rete.plot_graph(**kwargs)
        return filtered.reset_index(drop=True)

    def show_tree_selector(self, **kwargs):
        """
        Shows tree selector for event filtering, based on values in ``event_col`` column. It uses `_` for event splitting and aggregation, so ideally the event name structure in the dataset should include underscores, e.g. ``[section]_[page]_[action]``. In this case event names are separated into levels, so that all the events with the same ``[section]`` will be placed under the same section, etc.
        There two kind of checkboxes in IFrame: large blue and small white. The former are used to include or exclude event from original dataset. The latter are used for event aggregation: toggle on a checkbox to aggregate all the underlying events to this level.
        Tree filter has a download button in the end of event list, which downloads a JSON config file, which you then need to use to filter and aggregate events with ``BaseDataset.rete.use_tree_filter()`` method.

        Parameters
        --------
        event_col: str, optional
            Name of custom event column, for more information refer to ``init_config``. For instance, you may want to aggregate some events or rename and use it as new event column. By default the column defined in ``init_config`` will be used as ``event_col``.
        width: int, optional
            Width of IFrame object with filters.
        height: int, optional
            Height of IFrame object with filters.

        Returns
        --------
        Renders events tree selector

        Return type
        --------
        IFrame
        """
        self._init_cols(locals())
        from retentioneering.core.tree_selector import show_tree_filter
        show_tree_filter(self._obj[self._event_col()], **kwargs)

    def use_tree_filter(self, path, **kwargs):
        """
        Uses generated with ``show_tree_filter()`` JSON config to filter and aggregate ``event_col`` values of dataset.

        Parameters
        --------
        path: str
            Path to JSON config file generated with ``show_tree_filter()`` method.

        Returns
        --------
        Filtered and aggregated dataset

        Return type
        --------
        pd.DataFrame
        """
        from retentioneering.core.tree_selector import use_tree_filter
        res = use_tree_filter(self._obj, path, **kwargs)
        return res

    def _create_bins(self, data, time_step, index_col=None):
        self._init_cols(locals())
        tmp = data.join(
            data.groupby(self._index_col())
            [self._event_time_col()].min(),
            on=self._index_col(), rsuffix='_min')

        data['bins'] = (
                data[self._event_time_col()] - tmp[self._event_time_col() + '_min']
        )
        data['bins'] = np.floor(data['bins'] / np.timedelta64(1, time_step))

    def survival_curves(self, groups, spec_event=None, time_min=None, time_max=None, event_col=None, index_col=None,
                        target_event=None, time_step='D', plotting=True, **kwargs):
        """
        Plot survival curves for given grouping.

        Parameters
        --------
        groups: np.array
            Array of clickstream shape that splits data into different groups.
        spec_event: str, optional
            Event specific for test, e.g. we change auth flow, so we need to compare only users, who have started authorization, in this case `spec_event='auth_start'`. Default: ``None``
        time_min: int, optional
            Time when A/B test was started. If ``None``, then whole dataset is used. Defaul: ``None``
        time_max: int, optional
            Time when A/B test was ended. If ``None``, then whole dataset is used. Default: ``None``
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.
        event_col: str, optional
            Name of custom event column, for more information refer to ``init_config``. For instance, you may want to aggregate some events or rename and use it as new event column. By default the column defined in ``init_config`` will be used as ``event_col``.
        target_event: str, optional
            Name of target event. If ``None``, then taken from ``retention_config``. Default: ``None``
        time_step: str, optional
            Time step for calculation of survival rate at specific time.
                Possible options:
                    (`'D'` -- day, `'M'` -- month, `'h'` -- hour, `'m'` -- minute, `'Y'` -- year,
                     `'W'` -- week, `'s'` -- seconds, `'ms'` -- milliseconds).
            Default is day (`'D'`).
        plotting: bool, optional
            If ``True``, then plots survival curves.

        Returns
        --------
        Dataframe with points at survival curves and prints chi-squared LogRank test for equality statistics.

        Return type
        -------
        pd.DataFrame
        """
        self._init_cols(locals())
        data = self._obj.copy()
        if spec_event is not None:
            users = (data[data[self._event_col()]== spec_event][self._index_col()]).unique()
            f = data[self._index_col()].isin(users)
            data = data[f].copy()
            groups = groups[f].copy()
        if type(data[self._event_time_col()].iloc[0]) not in (int, float, object, str):
            data[self._event_time_col()] = pd.to_datetime(
                data[self._event_time_col()])
        if time_min is not None:
            f = data[self._event_time_col()] >= pd.to_datetime(time_min)
            data = data[f].copy()
            groups = groups[f].copy()
        if time_max is not None:
            f = data[self._event_time_col()] <= pd.to_datetime(time_max)
            data = data[f].copy()
            groups = groups[f].copy()
        self._create_bins(data, time_step, index_col)

        data['metric_col'] = (data
                              [self._event_col()]
                              == (target_event or self.retention_config['positive_target_event']))
        tmp = data[data.metric_col == 1]
        curves = tmp.groupby(
            [groups, 'bins']
        )[self._index_col()].nunique().rename('metric').reset_index()
        curves = curves.sort_values('bins', ascending=False)
        curves['metric'] = curves.groupby(groups.name).metric.cumsum()
        curves = curves.sort_values('bins')
        res = (curves
               .merge(curves
                      .groupby(groups.name)
                      .head(1)[[groups.name, 'metric']],
                      on=groups.name, suffixes=('', '_max')))
        self._logrank_test(res, groups.name)
        res['metric'] = res.metric / res.metric_max
        if plotting:
            plot.sns.lineplot(data=res, x='bins', y='metric', hue=groups.name)
        return res

    @staticmethod
    def _logrank_test(x, group_col):
        x['next_metric'] = x.groupby(group_col).metric.shift(-1)
        x['o'] = (x['metric'] - x['next_metric'])
        oj = x.groupby('bins').o.sum()
        nj = x.groupby('bins').metric.sum()
        exp = (oj / nj).rename('exp')
        x = x.join(exp, on='bins')
        x1 = x[x[group_col]]
        x1.index = x1.bins
        up = (x1.o - x1.exp * x1.metric).sum()
        var = ((oj * (x1.metric / nj) * (1 - x1.metric / nj) * (nj - oj)) / (nj - 1)).sum()
        z = up ** 2 / var

        from scipy.stats import chi2
        pval = 1 - chi2.cdf(z, df=1)
        print(f"""
        There is {'' if pval <= 0.05 else 'no '}significant difference
        log-rank chisq: {z}
        P-value: {pval}
        """)

    def index_based_split(self, index_col=None, test_size=0.2, seed=0):
        """
        Splits dataset between train and test based on ``index_col``.

        Parameters
        -------
        index_col: str, optional
            Name of custom index column, for more information refer to ``init_config``. For instance, if in config you have defined ``index_col`` as ``user_id``, but want to use function over sessions. By default the column defined in ``init_config`` will be used as ``index_col``.
        test_size: float, optional
            Rate of test subsample from 0 to 1. Default: ``0.2``
        seed: int, optional
            Random seed number. Default: ``0``

        Returns
        -------
        Two dataframes: train and test.

        Return type
        -------
        pd.DataFrame
        """
        self._init_cols(locals())
        np.random.seed(seed)
        ids = np.random.permutation(self._obj[self._index_col()].unique())
        f = self._obj[self._index_col()].isin(ids[int(ids.shape[0] * test_size):])
        return self._obj[f].copy(), self._obj[~f].copy()

    def step_matrix_bootstrap(self, n_samples=10, sample_size=None, sample_rate=1, random_state=0, **kwargs):
        """
        Estimates means and standard deviations of step matrix values with bootstrap.

        Parameters
        --------
        n_samples: int, optional
            Number of samples for bootstrap. Default: ``10``
        sample_size: int, optional
            Size of each subsample. Default: ``None``
        sample_rate: float, optional
            Rate of each subsample. Note that it cannot be used with ``sample_size``. Default: ``1``
        random_state: int, optional
            Random state for sampling. Default: ``0``
        kwargs: optional
            Arguments of ``BaseDataset.rete.get_step_matrix()``

        Returns
        --------
        Two dataframes: with mean and standard deviation values.

        Return type
        --------
        pd.DataFrame
        """
        self._init_cols(locals())
        res = []
        base = pd.DataFrame(0,
                            index=self._obj[self._event_col()].unique(),
                            columns=range(1, kwargs.get('max_steps') or 31)
                            )
        thr = kwargs.pop('thr', None)
        plot_type = kwargs.pop('plot_type', None)
        for i in range(n_samples):
            tmp = self._obj.sample(n=sample_size, frac=sample_rate, replace=True, random_state=random_state + i)
            tmp = (tmp.rete.get_step_matrix(plot_type=False, **kwargs) + base).fillna(0)
            tmp = tmp.loc[base.index.tolist()]
            res.append(tmp.values[:, :, np.newaxis])
        kwargs.update({'thr': thr})
        res = np.concatenate(res, axis=2)
        piv = pd.DataFrame(res.mean(2), index=base.index, columns=base.columns)
        stds = pd.DataFrame(res.std(2), index=base.index, columns=base.columns)

        if not kwargs.get('reverse'):
            for i in self.retention_config['target_event_list']:
                piv = piv.append(self._add_accums(piv, i))
        if kwargs.get('thr'):
            thr = kwargs.pop('thr')
            piv = self._process_thr(piv, thr, kwargs.get('max_steps' or 30), **kwargs)
        if kwargs.get('sorting'):
            piv = self._sort_matrix(piv)
        if not kwargs.get('for_diff'):
            if kwargs.get('reverse'):
                piv.columns = ['n'] + ['n - {}'.format(i - 1) for i in piv.columns[1:]]
        if plot_type:
            plot.step_matrix(
                piv.round(2),
                title=kwargs.get('title',
                                 'Step matrix {}'
                                 .format('reversed' if kwargs.get('reverse') else '')), **kwargs)
            plot.step_matrix(
                stds.round(3),
                title=kwargs.get('title',
                                 'Step matrix std'), **kwargs)
        if kwargs.get('dt_means') is not None:
            means = np.array(self._obj.groupby('event_rank').apply(
                lambda x: (x.next_timestamp - x.event_timestamp).dt.total_seconds().mean()
            ))
            piv = pd.concat([piv, pd.DataFrame([means[:kwargs.get('max_steps' or 30)]],
                                               columns=piv.columns, index=['dt_mean'])])
        return piv, stds

    def core_event_distribution(self, core_events, index_col=None, event_col=None,
                                thresh=None, plotting=True, use_greater=True, **kwargs):
        self._init_cols(locals())
        if type(core_events) == str:
            core_events = [core_events]
        self._obj['is_core_event'] = self._obj[self._event_col()].isin(core_events)
        rates = self._obj.groupby(self._index_col()).is_core_event.mean()
        if plotting:
            plot.core_event_dist(rates, thresh, **kwargs)
        if use_greater:
            f = set(rates[rates >= thresh].index.values)
        else:
            f = set(rates[rates < thresh].index.values)
        return self._obj[self._obj[self._index_col()].isin(f)].reset_index(drop=True)

    def pairwise_time_distribution(self, event_order, time_col=None, index_col=None,
                                   event_col=None, bins=100, limit=180, topk=3):
        self._init_cols(locals())
        if 'next_event' not in self._obj.columns:
            data = self.get_shift(index_col=index_col,
                                  event_col=event_col).copy()

        data['time_diff'] = (data['next_timestamp'] - data[
            time_col or self.retention_config['event_time_col']]).dt.total_seconds()
        f_cur = data[self._event_col()] == event_order[0]
        f_next = data['next_event'] == event_order[1]
        s_next = data[f_cur & f_next].copy()
        s_cur = data[f_cur & (~f_next)].copy()

        s_cur.time_diff[s_cur.time_diff < limit].hist(alpha=0.5, log=True,
                                                      bins=bins, label='Others {:.2f}'.format(
                                                          (s_cur.time_diff < limit).sum() / f_cur.sum()
                                                      ))
        s_next.time_diff[s_next.time_diff < limit].hist(alpha=0.7, log=True,
                                                        bins=bins,
                                                        label='Selected event order {:.2f}'.format(
                                                            (s_next.time_diff < limit).sum() / f_cur.sum()
                                                        ))
        plot.sns.mpl.pyplot.legend()
        plot.sns.mpl.pyplot.show()
        (s_cur.next_event.value_counts() / f_cur.sum()).iloc[:topk].plot.bar()



    @staticmethod
    def _find_traj(x, event_list, event_col):
        res = np.ones_like(x[event_col]).astype(bool)
        for elem in event_list:
            res &= ((x[event_col] == elem).cumsum() > 0).values
        return res.max()

    def create_trajectory_filter(self, event_list, index_col=None, event_col=None, **kwargs):
        self._init_cols(locals())
        df_stat = (self
                   ._obj
                   .groupby(self._index_col())
                   .apply(self._find_traj,
                          event_list=event_list,
                          event_col=self._event_col()))
        return df_stat

    def apply_trajectory_filter(self, event_list, index_col=None, event_col=None, **kwargs):
        self._init_cols(locals())
        f = self.create_trajectory_filter(event_list, index_col, event_col, **kwargs)
        f = self._obj[self._index_col()].isin(f[f].index.tolist())
        return self._obj[f].copy().reset_index(drop=True)

    def _is_cycle(self, data):
        """
            Utilite for cycle search
        """
        temp = data.split('~~')
        return True if temp[0] == temp[-1] and len(set(temp)) > 1 else False

    def _is_loop(self, data):
        """
            Utilite for loop search
        """
        temp = data.split('~~')
        return True if len(set(temp)) == 1 else False

    def get_equal_fraction(self, fraction=1, random_state=42):
        """
            Selects fraction of good users and the same number of bad users

            Parameters
            --------
            fraction: float, optional
                Fraction of users. Should be in interval of (0,1]
            random_state: int, optional
                random state for numpy choice function

            Returns
            --------
            Two dataframes: with good and bad users

            Return type
            --------
            tuple of pd.DataFrame
        """
        if fraction <= 0 or fraction > 1:
            raise ValueError('The fraction is <= 0 or > 1')
        self._init_cols(locals())

        np.random.seed(random_state)
        good_users = self.get_positive_users()
        bad_users = self.get_negative_users()

        sample_size = min(int(len(good_users) * fraction), len(bad_users))
        good_users_sample = set(np.random.choice(good_users, sample_size, replace=False))
        bad_users_sample = set(np.random.choice(bad_users, sample_size, replace=False))

        return (self._obj[self._obj[self._index_col()].isin(good_users_sample)],
                self._obj[self._obj[self._index_col()].isin(bad_users_sample)])

    def _remove_duplicates(self, data):
        """
        Removing same events, that are going one after another
        ('ev1 -> ev1 -> ev2 -> ev1 -> ev3 -> ev3   --------> ev1 -> ev2 -> ev1 -> ev3').
        This utilite is used in a find_sequences function

        """
        t = data.split('~~')
        t = '~~'.join([t[0]] + ['~~'.join(word for ind, word in enumerate(t[1:]) if t[ind] != t[ind + 1])])
        return t[:-2] if t[-1] == '~' else t

    def find_sequences(self, ngram_range=(1, 1), fraction=1, random_state=42, exclude_cycles=False, exclude_loops=False,
                       exclude_repetitions=False,threshold = 0, coefficient = 0):
        """
            Finds all subsequences of length lying in interval

            Parameters
            --------
            fraction: float, optional
                Fraction of users. Should be in interval of (0,1]
            random_state: int, optional
                random state for numpy choice function

            Returns
            --------
            Two dataframes: with good and bad users

            Return type
            --------
            tuple of pd.DataFrame
        """
        self._init_cols(locals())
        sequences = dict()
        good, bad = self.get_equal_fraction(fraction, random_state)
        countvect = CountVectorizer(ngram_range=ngram_range,token_pattern = '[^~]+')
        good_corpus = good.groupby(self._index_col())[self._event_col()].apply(
            lambda x: '~~'.join([l.lower() for l in x if l != 'pass' and l != 'lost']))
        good_count = countvect.fit_transform(good_corpus.values)
        good_frame = pd.DataFrame(columns=['~~'.join(x.split(' ')) for x in countvect.get_feature_names()],
                                  data=good_count.todense())
        bad_corpus = bad.groupby(self._index_col())[self._event_col()].apply(
            lambda x: '~~'.join([l.lower() for l in x if l != 'pass' and l != 'lost']))
        bad_count = countvect.fit_transform(bad_corpus.values)
        bad_frame = pd.DataFrame(columns=['~~'.join(x.split(' ')) for x in countvect.get_feature_names()],
                                 data=bad_count.todense())

        res = pd.concat([good_frame.sum(), bad_frame.sum()], axis=1).fillna(0).reset_index()
        res.columns = ['Sequence', 'Good', 'Lost']

        if exclude_cycles:
            res = res[~res.Sequence.apply(lambda x: self._is_cycle(x))]
        if exclude_loops:
            temp = res[~res.Sequence.apply(lambda x: self._is_loop(x))]
        if exclude_repetitions:
            res.Sequence = res.Sequence.apply(lambda x: self._remove_duplicates(x))
            res = res.groupby(res.Sequence)[['Good', 'Lost']].sum().reset_index()
            res = res[res.Sequence.apply(lambda x: len(x.split('~~')) in range(ngram_range[0],ngram_range[1] + 1))]

        res['Lost2Good'] = res['Lost'] / res['Good']
        return res[(abs(res['Lost2Good'] - 1) > coefficient) & (res.Good + res.Lost > threshold)]\
            .sort_values('Lost', ascending=False).reset_index(drop=True)

    def find_cycles(self, interval, fraction=1, random_state=42, exclude_loops=False, exclude_repetitions=False):
        """

        Parameters
        ----------
        interval - interval of lengths for search. Any int number
        fraction - fraction of good users. Any float in (0,1]
        random_state - random_state for numpy random seed

        Returns pd.DataFrame with cycles
        -------

        """
        self._init_cols(locals())
        temp = self.find_sequences(interval, fraction, random_state, exclude_loops=exclude_loops,
                                   exclude_repetitions=exclude_repetitions).reset_index(drop=True)
        return temp[temp['Sequence'].apply(lambda x: self._is_cycle(x))].reset_index(drop=True)

    def find_loops(self, fraction=1, random_state=42):
        """
        Function for loop searching
        Parameters
        ----------
        fraction - fraction of good users. Any float in (0,1]
        random_state - random_state for numpy random seed

        Returns pd.DataFrame with loops. Good, Lost columns are for all occurences,
        (Good/Lost)_no_duplicates are for counting each cycle only once for user in which they occur
        -------

        """
        def loop_search(data, self_loops, event_list, is_bad):
            self._init_cols(locals())
            event_list = {k: 0 for k in event_list}
            for ind, url in enumerate(data[1:]):
                if data[ind] == data[ind + 1]:
                    if url in self_loops.keys():
                        self_loops[url][is_bad] += 1
                        if event_list[url] == 0:
                            self_loops[url][is_bad + 3] += 1
                            event_list[url] = 1
                    else:
                        self_loops[url] = [0, 0, 0, 0, 0, 0]
                        self_loops[url][is_bad] = 1
                        if event_list[url] == 0:
                            self_loops[url][is_bad + 3] += 1
                            event_list[url] = 1

        self._init_cols(locals())
        self_loops = dict()
        event_list = self._obj[self._event_col()].unique()
        good, bad = self.get_equal_fraction(fraction, random_state)
        for el in good.groupby(self._index_col()):
            loop_search(el[1][self._event_col()].values, self_loops, event_list, 0)

        for el in bad.groupby(self._index_col()):
            loop_search(el[1][self._event_col()].values, self_loops, event_list, 1)

        for key, val in self_loops.items():
            if val[0] != 0:
                self_loops[key][2] = val[1] / val[0]
            if val[3] != 0:
                self_loops[key][5] = val[4] / val[3]

        return pd.DataFrame(data=[[a[0]] + a[1] for a in self_loops.items()],
                            columns=['Sequence', 'Good', 'Lost', 'Lost2Good', 'GoodUnique',
                                     'LostUnique', 'UniqueLost2Good'])\
            .sort_values('Lost', ascending=False).reset_index(drop=True)

    @staticmethod
    def _create_diff_index(desc_old, desc_new):
        old_id = set(desc_old.index)
        new_id = set(desc_new.index)

        if old_id != new_id:
            for idx in new_id - old_id:
                row = pd.Series([0] * desc_old.shape[1], name=idx)
                row.index += 1
                desc_old = desc_old.append(row, sort=True)
            for idx in old_id - new_id:
                row = pd.Series([0] * desc_new.shape[1], name=idx)
                row.index += 1
                desc_new = desc_new.append(row, sort=True)
        return desc_old, desc_new

    @staticmethod
    def _diff_step_allign(desc_old, desc_new):
        max_old = desc_old.shape[1]
        max_new = desc_new.shape[1]
        if max_old < max_new:
            for i in range(max_old, max_new + 1):
                desc_old[i] = np.where(desc_old.index.str.startswith('Accumulated'), desc_old[i - 1], 0)
        elif max_old > max_new:
            for i in range(max_new, max_old + 1):
                desc_new[i] = np.where(desc_new.index.str.startswith('Accumulated'), desc_new[i - 1], 0)
        return desc_old, desc_new