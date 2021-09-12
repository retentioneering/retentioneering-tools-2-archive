# * Copyright (C) 2020 Maxim Godzi, Anatoly Zaytsev, Retentioneering Team
# * This Source Code Form is subject to the terms of the Retentioneering Software Non-Exclusive License (License)
# * By using, sharing or editing this code you agree with the License terms and conditions.
# * You can obtain License text at https://github.com/retentioneering/retentioneering-tools/blob/master/LICENSE.md


__RENDER_INNER_IFRAME__ = """
<iframe id="{id}" src="about:blank" width="{width}" height="{height}">
</iframe>
<script>
   (function() {{
      const iframeDocument = document.getElementById(`{id}`).contentDocument
      iframeDocument.body.innerHTML = `{graph_body}`

      const styles = iframeDocument.createElement("style")
      styles.innerHTML = `{graph_styles}`

      const graphScript = iframeDocument.createElement("script")
      graphScript.src = `{graph_script_src}`

      graphScript.addEventListener("load", () => {{
        const initGraph = iframeDocument.createElement("script")
        initGraph.innerHTML = `{init_graph_js}`

        iframeDocument.body.appendChild(initGraph)
      }})

      iframeDocument.head.appendChild(styles)
      iframeDocument.head.appendChild(graphScript)
   }})()
</script>
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
    initialize({{
      serverId: {server_id},
      env: {env},
      configNodes: {nodes},
      configLinks: {links},
      nodesColsNames: {node_cols_names},
      linksWeightsNames: {links_weights_names},
      nodesThreshold: {nodes_threshold},
      linksThreshold: {links_threshold},
      useLayoutDump: Boolean({layout_dump}),
      weightTemplate: {weight_template},
    }})
"""
