# * Copyright (C) 2020 Maxim Godzi, Anatoly Zaytsev, Retentioneering Team
# * This Source Code Form is subject to the terms of the Retentioneering Software Non-Exclusive License (License)
# * By using, sharing or editing this code you agree with the License terms and conditions.
# * You can obtain License text at https://github.com/retentioneering/retentioneering-tools/blob/master/LICENSE.md


__RENDER_INNER_IFRAME__ = """
<iframe id="{id}" src="about:blank" width="{width}" height="{height}">
</iframe>
<script>
   (function() {{
      console.log('init iframe')
      console.log(`{id}`)
      debugger
      const iframeDocument = document.getElementById(`{id}`).contentDocument
      console.log(iframeDocument.body)
      iframeDocument.body.innerHTML = `{graph_body}`

      console.log('set html')
      const styles = iframeDocument.createElement("style")
      styles.innerHTML = `{graph_styles}`


      const graphScript = iframeDocument.createElement("script")
      graphScript.src = `{graph_script_src}`

      graphScript.addEventListener("load", () => {{
        console.log('graph script load')
        const initGraph = iframeDocument.createElement("script")
        initGraph.innerHTML = `{init_graph_js}`

        iframeDocument.body.appendChild(initGraph)
      }})

      console.log('add graph script')
      iframeDocument.head.appendChild(styles)
      iframeDocument.head.appendChild(graphScript)

      iframeDocument.body.dataset.templateId = '{id}_template'
      console.log('init end')
   }})()
</script>
<template id="{id}_template">
  {template}
</template>
"""

__GRAPH_STYLES__ = """
    .svg-watermark {{
      width: 100%;
      font-size: 80px;
      fill: #c2c2c2;
      opacity: 0.3;
      font-family: Arial;
    }}

    .link {{
      fill: none;
      stroke: #666;
      stroke-opacity: 0.7;
    }}

    text {{
      font: 12px sans-serif;
      pointer-events: none;
    }}

    circle {{
      fill: #ccc;
      stroke: #333;
      stroke-width: 1.5px;
    }}

    .selected-node {{
      stroke: blue;
      stroke-width: 3px;
    }}

    .circle.source_node {{
      fill: #f3f310;
    }}

    .circle.nice_node {{
      fill: green;
    }}

    .circle.bad_node {{
      fill: red;
    }}
"""

__GRAPH_BODY__ = """
  <div id="root"></div>
"""

__INIT_GRAPH__ = """
    console.log('init graph')
    debugger
    initialize({{
      serverId: {server_id},
      env: {env},
      configNodes: {nodes},
      configLinks: {links},
      nodesColsNames: {node_cols_names},
      linksWeightsNames: {links_weights_names},
      nodesThreshold: {nodes_threshold},
      linksThreshold: {links_threshold},
      showWeights: {show_weights},
      showPercents: {show_percents},
      showNodesNames: {show_nodes_names},
      showAllEdgesForTargets: {show_all_edges_for_targets},
      showNodesWithoutLinks: {show_nodes_without_links},
      useLayoutDump: Boolean({layout_dump}),
      weightTemplate: {weight_template},
    }})
"""


__FULL_HTML__ = """
  <!DOCTYPE html>
  <html lang="en">
  <head>
    <meta charset="utf-8">
    <title>Rete graph</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
  </head>
  <body>
    {content}
  </body>
  </html>
"""
