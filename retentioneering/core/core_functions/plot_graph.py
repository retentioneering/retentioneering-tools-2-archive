# * Copyright (C) 2020 Maxim Godzi, Anatoly Zaytsev, Retentioneering Team
# * This Source Code Form is subject to the terms of the Retentioneering Software Non-Exclusive License (License)
# * By using, sharing or editing this code you agree with the License terms and conditions.
# * You can obtain License text at https://github.com/retentioneering/retentioneering-tools/blob/master/LICENSE.md

from retentioneering.visualization import draw_graph
from IPython.display import display, HTML


def plot_graph(self, *,
               targets={},
               weight_cols=None,
               norm_type='full',
               layout_dump=None,
               width=960,
               height=740,
               nodes_threshold=None,
               links_threshold=None):
    """
    Create interactive graph visualization. Each node is a unique event_col
    value, edges are transitions between events and edge weights are calculated
    metrics. By default, it is a percentage of unique users that have passed
    though a particular edge visualized with the edge thickness. Node sizes are
    Graph loop is a transition to the same node, which may happen if users
    encountered multiple errors or made any action at least twice. Graph nodes
    are movable on canvas which helps to visualize user trajectories but is also
    a cumbersome process to place all the nodes so it forms a story.

    That is why IFrame object also has a download button. By pressing it, a JSON
    configuration file with all the node parameters is downloaded. It contains
    node names, their positions, relative sizes and types. It it used as
    layout_dump parameter for layout configuration. Finally, show weights
    toggle shows and hides edge weights.

    Parameters
    ----------
    norm_type: str (optional, default 'full')
        Type of normalization used to calculate weights for graph edges. Possible
        values are:
            * None
            * 'full'
            * 'node'

    weight_col: str (optional, default None)
        Aggregation column for edge weighting. If None, number of events will be
        calculated. For example, can be specified as `client_id` or `session_id`
        if dataframe has such columns.

    targets: dict (optional, default None)
        Event mapping describing which nodes or edges should be highlighted by
        different colors for better visualisation. Dictionary keys are event_col
        values, while keys have the following possible values:
        Example: {'lost': 'red', 'purchased': 'green', 'main': 'source'}

    thresh: float (optional, default 0.01)
        Minimal edge weight value to be rendered on a graph. If a node has no
        edges of the weight >= thresh, then it is not shown on a graph. It
        is used to filter out rare event and not to clutter visualization. Nodes
        specified in targets parameter will be always shown regardless selected
        threshold.

    layout_dump: str (optional, default None)
        Path to layout configuration file relative to current directory. If
        defined, uses configuration file as a graph layout.

    width: int (optional, default 800)
        Width of plot in pixels.

    height: int (optional, default 500)
        Height of plot in pixels.

    Returns
    -------
    Plots IFrame graph of width and height size.
    Saves webpage with JS graph visualization to
    retention_config.experiments_folder.

    Return type
    -----------
    Renders IFrame object and saves graph visualization as HTML in
    experiments_folder of retention_config.
    """

    event_col = self.retention_config['event_col']

    # TODO: change downstream processing
    if targets is not None:
        for k, v in targets.items():
            if v == 'red':
                v = 'bad_target'
            if v == 'green':
                v = 'nice_target'
            targets[k] = v

    nodes_df = self._obj[event_col].value_counts()
    nodes_scale = nodes_df.abs().max()

    node_weights = nodes_df.to_dict()
    data = self.get_graph_edgelist(weight_cols=weight_cols,
                             norm_type=norm_type)

    interactive = True
    try:
        import google.colab
        interactive = False
    except:
        pass

    path = draw_graph.graph(data,
                            node_params=targets,
                            node_weights=node_weights,
                            layout_dump=layout_dump,
                            weight_cols=weight_cols,
                            width=width,
                            height=height,
                            interactive=interactive,
                            nodes_scale=nodes_scale,
                            nodes_threshold=nodes_threshold,
                            links_threshold=links_threshold)

    # if work from google colab user HTML display:
    if interactive == False:
        display(HTML(path))
        return

    return path
