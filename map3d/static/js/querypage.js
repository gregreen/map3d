(function() {
"use strict"

var utils = (function() {
  // Fire listener only every <timeout> milliseconds, at the most
  var debounce = function(fn, timeout) {
    var timeoutID = -1;
    return function() {
      if (timeoutID > -1) {
        window.clearTimeout(timeoutID);
      }
      timeoutID = window.setTimeout(fn, timeout);
    }
  };

  // Return absolute (left, top, width, height) of a DOM element, in px.
  var get_obj_dimensions = function(obj) {
    var xy0 = $(obj).position();
    var x0 = xy0.left;
    var y0 = xy0.top;

    x0 += parseInt($(obj).css("padding-left"), 10);
    y0 += parseInt($(obj).css("padding-top"), 10);

    x0 += parseInt($(obj).css("margin-left"), 10);
    y0 += parseInt($(obj).css("margin-top"), 10);

    var w = parseInt($(obj).css("width"), 10);
    var h = parseInt($(obj).css("height"), 10);

    return {
      "left": x0,
      "top": y0,
      "width": w,
      "height": h
    };
  };

  return {
    "debounce": debounce,
    "get_obj_dimensions": get_obj_dimensions
  };
})();

function create_plot() {
  /*
   * Warning/Error messages to user.
   */

  // Show a custom warning message at the top of the page
  var show_custom_alert = function(msg) {
    var alert_div = d3.select("#custom-alert-div");
    var prev_msg = alert_div.select("h4").text();

    var exec_show = function() {
      alert_div.select("h4").text(msg);
      $("#custom-alert-div").collapse("show")
      alert_div.transition().duration(200)
        .style("opacity", 1);
    };

    if (d3.select("#custom-alert-div").classed("collapse in")) {
      if (prev_msg == msg) {
        return;
      } else {
        $("#custom-alert-div").on("hidden.bs.collapse", function() {
          exec_show();
        });
        $("#custom-alert-div").collapse("hide");
      }
    } else {
      exec_show();
    }
  };

  // Hide custom warning message
  var hide_custom_alert = function() {
    if (!d3.select("#custom-alert-div").classed("collapse in")) {
      return;
    }
    $("#custom-alert-div").collapse("hide");
    d3.select("#custom-alert-div")
      .transition().duration(200)
      .style("opacity", 0);
    console.log("hiding");
  };

  // Show an error about bad coordinates
  var show_bad_coords_alert = function(msg) {
    d3.select("#bad-coords-alert").selectAll("div")
      .classed("no-display", true);
    if (msg === "lon") {
      msg = "Invalid longitude specification.";
      d3.select("#bad-coords-alert").select("#lon-examples")
        .classed("no-display", false);
    } else if (msg === "lat") {
      msg = "Invalid latitude specification.";
      d3.select("#bad-coords-alert").select("#lat-examples")
        .classed("no-display", false);
    }
    d3.select("#bad-coords-div").select("h3").text(msg);
    $("#bad-coords-div").collapse("show")
    d3.select("#bad-coords-div")
      .transition().duration(200)
      .style("opacity", 1);
  };

  // Hide the bad coordinates error
  var hide_bad_coords_alert = function() {
    if (!d3.select("#bad-coords-div").classed("collapse in")) {
      return;
    }
    $("#bad-coords-div").collapse("hide");
    d3.select("#bad-coords-div")
      .transition().duration(200)
      .style("opacity", 0);
  };

  /*
   * Set/Get coordinates
   */

  // Returns true if coordinates are valid.
  // Issues appropriate warnings to user
  var issue_coord_warnings = function(coords) {
    if (coords.lon.val === null) {
      hide_custom_alert();
      show_bad_coords_alert("lon");
      return false
    } else if (coords.lat.val === null) {
      hide_custom_alert();
      show_bad_coords_alert("lat");
      return false;
    } else if ((coords.lat.val < -90) || (coords.lat.val > 90)) {
      hide_custom_alert();
      show_bad_coords_alert("Latitude outside domain [-90, 90].");
      return false;
    } else {
      hide_bad_coords_alert();
    }

    if ((coords.coord_sys === "gal") & (coords.lon.format === "hms")) {
      show_custom_alert("hh:mm:ss format detected in lontitude. Did you mean to use Equatorial coordinates?");
    } else if ((coords.coord_sys === "gal")
             & (coords.lat.format == "dms")) {
      show_custom_alert("dd:mm:ss format detected in latitude. Did you mean to use Equatorial coordinates?");
    } else {
      hide_custom_alert();
    }

    return true;
  };

  // Set the coordinate system to either "gal" or "equ"
  var set_coordsys = function(c) {
    if(c === "gal") {
      d3.select("#gal-l-input")
        .attr("placeholder", "lon. (\u00B0)");
      d3.select("#gal-b-input")
        .attr("placeholder", "lat. (\u00B0)");
      d3.select("#gal-l-symbol")
        .text("\u2113");
      d3.select("#gal-b-symbol")
        .text("b");
      d3.select("#submit-btn")
        .classed("btn-success", true);
      d3.select("#submit-btn")
        .classed("btn-primary", false);
      d3.select("#enter-coords-alert")
        .classed("alert-success", true);
      d3.select("#enter-coords-alert")
        .classed("alert-info", false);
    } else if(c === "equ") {
      d3.select("#gal-l-input")
        .attr("placeholder", "R.A.");
      d3.select("#gal-b-input")
        .attr("placeholder", "Dec.");
      d3.select("#gal-l-symbol")
        .text("\u03B1");
      d3.select("#gal-b-symbol")
        .text("\u03B4");
      d3.select("#submit-btn")
        .classed("btn-success", false);
      d3.select("#submit-btn")
        .classed("btn-primary", true);
      d3.select("#enter-coords-alert")
        .classed("alert-success", false);
      d3.select("#enter-coords-alert")
        .classed("alert-info", true);
    } else {
      console.log("Unknown coordinate system: " + c);
      return;
    }
  };

  var get_coord_sys = function() {
    return $("#coord-toggle").prop("checked") ? "gal" : "equ";
  };

  // Read the input boxes to get the coordinates
  var get_coordinates = function() {
    var coord_sys = get_coord_sys();
    var lon = astrocoords.parse_angle(
      $('input[name="gal-l"]').val(),
      true  // Hour-minute-second possible
    );
    var lat = astrocoords.parse_angle(
      $('input[name="gal-b"]').val(),
      false // Hour-minute-deg possible
    );
    return {
      "coord_sys": coord_sys,
      "lon": lon,
      "lat": lat
    };
  };

  /*
   * Distance - E(B-V) plot
   */

  var show_plot_div = function(callback) {
    if (d3.select("#line-plot-div").classed("in")) {
      callback();
      return;
    }
    if (callback) {
      $("#line-plot-div").on("shown.bs.collapse", function() {
        callback();
      });
    }
    $("#line-plot-div").collapse("show");
  };

  var plot_distance_reddening = function(query_data) {
    var dt = 500; // Transition speed (in ms)

    // Determine overall dimensions of plot
    var svg = d3.select("#distance-reddening-plot");
    var view_box = svg.attr("viewBox").split(" ").slice(2);
    var svg_width = view_box[0],
        svg_height = view_box[1];

    var margins = {
      "left": 0.10 * svg_width,
      "right": 0.05 * svg_width,
      "bottom": 0.10 * svg_width,
      "top": 0.02 * svg_width
    };

    var plot_width = svg_width - margins.right - margins.left,
        plot_height = svg_height - margins.top - margins.bottom;

    // Remove NaNs from data
    var remove_nans = function(arr) {
      return arr.map(function(a) {
        return a || 0;
      });
    };
    var samples = remove_nans(query_data.samples);
    var best = remove_nans(query_data.best);

    // Determine max y-value
    var y_max = d3.max(
      samples,
      function(row) { return d3.max(row); }
    );
    y_max = d3.max([y_max, d3.max(best)]);
    y_max = 1.2 * y_max + 0.01;

    // Convert between data (x, y) and SVG coordinates
    var scale_x = d3.scaleLinear()
      .domain(d3.extent(query_data.distmod))
      .range([0, plot_width]);

    var scale_y = d3.scaleLinear()
      .domain([0, y_max])
      .range([plot_height, 0]);

    // Definitions
    svg.selectAll("defs").data([null])
        .enter()
      .append("defs");

    // Add groups in correct order
    var main_group = svg.selectAll("#plot-main-group").data([null])
      .enter()
        .append("g")
          .attr("id", "plot-main-group");

    var plot_area_group = main_group.append("g")
      .attr("id", "plot-area")
      .attr("transform",
        "translate(" + margins.left + "," + margins.top + ")"
      );

    // Reliable distance range
    plot_area_group.append("g")
      .attr("id", "reliable-dist-group");

    // Distance-reddening lines
    plot_area_group.append("g")
      .attr("id", "plot-reddening-line-group");

    // Legend
    var legend_group = plot_area_group.append("g")
      .attr("id", "legend-group");

    // x-axis
    var x_axis = d3.select("#plot-main-group")
      .selectAll(".x.axis").data([null]);

    x_axis.enter()
      .append("g")
        .attr("class", "x axis")
        .attr("transform",
          "translate(" + margins.left + "," +
          (svg_height-margins.bottom) + ")"
        )
        .call(d3.axisBottom(scale_x))
      .append("text")
        .attr("class", "x axis-label")
        .attr("x", plot_width/2)
        .attr("dy", "38pt")
        .text("Distance Modulus (mag)");

    x_axis.transition().duration(dt)
      .call(d3.axisBottom(scale_x));

    x_axis.exit().remove();

    // y-axis
    var y_axis = d3.select("#plot-main-group")
      .selectAll(".y.axis").data([null]);

    y_axis.enter()
      .append("g")
        .attr("class", "y axis")
        .attr("transform",
          "translate(" + margins.left + "," +
                         margins.top + ")"
        )
        .call(d3.axisLeft(scale_y))
      .append("text")
        .attr("class", "y axis-label")
        .attr("x", -plot_height/2)
        .attr("y", 0)
        .attr("dy", "-52pt")
        .attr("transform", "rotate(-90)")
        .text("E(B-V) (mag)");

    y_axis.transition().duration(dt)
      .call(d3.axisLeft(scale_y));

    y_axis.exit().remove();

    // Function that creates SVG paths based on arrays
    var line = d3.line()
      .x(function(d) { return scale_x(d[0]); })
      .y(function(d) { return scale_y(d[1]); });

    // Add best-fit distance - reddening
    var best_line = svg.select("#plot-reddening-line-group")
      .selectAll("#best-line").data([
        d3.zip(query_data.distmod, best)
      ]);

    best_line.enter()
      .append("path")
      .attr("id", "best-line")
      .attr("class", "line best-line")
      .attr("d", line);

    best_line.transition().duration(dt)
      .attr("d", line);

    best_line.exit()
      .remove();

    // Add samples of distance - reddening
    var pack_data = function(x_vals, y_data) {
      return d3.range(y_data.length).map( function(idx) {
        return d3.zip(x_vals, y_data[idx]);
      });
    };

    var sample_line = svg.select("#plot-reddening-line-group")
      .selectAll(".sample-line").data(
        pack_data(query_data.distmod, samples)
      );

    sample_line.enter()
      .append("path")
      .attr("class", "line sample-line")
      .attr("d", line);

    sample_line.transition().duration(dt)
      .attr("d", line);

    sample_line.exit()
      .remove();

    // Create legend
    var legend_geom = {
      "width": 0.20 * plot_width,
      "height": 0.10 * plot_width,
      "bottom": 0.15 * plot_width,
      "right": 0.02 * plot_width
    };

    legend_group.attr(
      "transform",
      "translate(" +
        (plot_width - legend_geom.width - legend_geom.right) +
        "," +
        (plot_height - legend_geom.bottom) +
      ")"
    ).append("rect")
      .attr("id", "legend-frame")
      .attr("width", legend_geom.width)
      .attr("height", legend_geom.height);

    legend_group.append("text")
      .attr("id", "legend-best-label")
      .attr("x", 0.50*legend_geom.width)
      .attr("y", 0.10*legend_geom.height)
      .text("best fit");

    legend_group.append("text")
      .attr("id", "legend-sample-label")
      .attr("x", 0.50*legend_geom.width)
      .attr("y", 0.60*legend_geom.height)
      .text("samples");

    var legend_lines = legend_group.append("g")
      .attr("id", "legend-lines");

    // Add example "sample" and "best" lines to legend
    var add_legend_lines = function() {
      var legend_x = d3.range(0., 1.0, 0.20);
      var legend_best =     [ 0.70,  0.75,  0.75,   0.85,  1.00, 1.00];
      var legend_samples = [[ 0.10,  0.10,  0.15,   0.20,  0.25, 0.25],
                            [ 0.20,  0.25,  0.25,   0.30,  0.35, 0.35],
                            [ 0.00,  0.05,  0.30,   0.35,  0.40, 0.40]];

      var scale_x_legend = d3.scaleLinear()
        .domain([-0.1, 1.1])
        .range([0, 0.5*legend_geom.width]);
      var scale_y_legend = d3.scaleLinear()
        .domain([-0.1, 1.1])
        .range([legend_geom.height, 0]);

      var legend_gen_line = d3.line()
        .x(function(d) { return scale_x_legend(d[0]); })
        .y(function(d) { return scale_y_legend(d[1]); });

      legend_lines.selectAll(".legend-line-best")
        .data([d3.zip(legend_x, legend_best)])
          .enter()
        .append("path")
          .attr("class", "line best-line")
          .attr("d", legend_gen_line);

      legend_lines.selectAll(".legend-line-sample")
        .data(pack_data(legend_x, legend_samples))
          .enter()
        .append("path")
          .attr("class", "line sample-line")
          .attr("d", legend_gen_line);
    };

    add_legend_lines();

    // Reliable distance range
    var dm_panel_width = (function() {
      var dm_close = query_data.min_reliable_distmod || 0;
      var dm_far = query_data.max_reliable_distmod || 0;
      if ((dm_far === 0) || (dm_close === 0) || (dm_close > dm_far)) {
        return [plot_width, 0];
      }
      return [scale_x(dm_close), plot_width - scale_x(dm_far)];
    })();

    var dm_close_panel = d3.select("#reliable-dist-group")
      .selectAll("#DM-close-panel").data([null]);

    dm_close_panel.enter()
      .append("rect")
        .attr("id", "DM-close-panel")
        .attr("x", 0)
        .attr("y", 0)
        .attr("width", dm_panel_width[0])
        .attr("height", plot_height);

    dm_close_panel.transition().duration(dt)
      .attr("width", dm_panel_width[0])
      .attr("height", plot_height);

    dm_close_panel.exit().remove();

    var dm_far_panel = d3.select("#reliable-dist-group")
      .selectAll("#DM-far-panel").data([null]);

    dm_far_panel.enter()
      .append("rect")
        .attr("id", "DM-far-panel")
        .attr("x", plot_width - dm_panel_width[1])
        .attr("y", 0)
        .attr("width", dm_panel_width[1])
        .attr("height", plot_height);

    dm_far_panel.transition().duration(dt)
      .attr("x", plot_width - dm_panel_width[1])
      .attr("width", dm_panel_width[1])
      .attr("height", plot_height);

    dm_far_panel.exit().remove();

    // Diagonal hatch pattern
    var pattern_scale = 2,
        stroke_scale = 3;
    var path_str = function(cx, cy) {
      return pattern_scale*cx + "," + pattern_scale*cy;
    }

    svg.select("defs").selectAll("#diagonal-hatch").data([null])
        .enter()
      .append("pattern")
        .attr("id", "diagonal-hatch")
        .attr("patternUnits", "userSpaceOnUse")
        .attr("width", 4*pattern_scale)
        .attr("height", 4*pattern_scale)
      .append("path")
        .attr("d", "M" + path_str(-1,1) +
                   " l" + path_str(2,-2) +
                   " M" + path_str(0,4) +
                   " l" + path_str(4,-4) +
                   " M" + path_str(3,5) +
                   " l" + path_str(2,-2))
        .attr("stroke", "#000")
        .attr("stroke-width", stroke_scale);

    // Label on top of reliable distance indicators

    // Background for text that hollows-out hatch pattern
    var dm_label_data = [
      ["close", "No Stars"],
      ["far", "No MS Stars"]
    ];

    var rel_dist_masks = svg.select("defs")
      .selectAll(".rel-dist-mask")
      .data(dm_label_data);

    var rel_dist_masks_enter = rel_dist_masks.enter()
      .append("mask")
        .attr("id", function(d) { return d[0] + "-label-mask"; })
        .attr("class", "rel-dist-mask");

    rel_dist_masks_enter.append("rect")
      .attr("id", function(d) { return d[0] + "-label-bkgd"; })
      .attr("class", "rel-dist-label-bkgd")
      .attr("x", 0)
      .attr("y", 0)
      .attr("width", "100%")
      .attr("height", "100%");

    // Text to hollow-out hatch pattern
    var get_dm_label_transform = function(d) {
      var dx = null,
          dy = plot_height/2;
      if (d[0] === "close") {
        dx = dm_panel_width[0]/2;
      } else if (d[0] === "far") {
        dx = 1.02 * plot_width - dm_panel_width[1];
        if (dm_panel_width[1] === 0) {
          dx += plot_width;
        }
      }
      return "translate("+dx+","+dy+") "+"rotate(-90)";
    };

    rel_dist_masks_enter.append("text")
      .attr("id", function(d) { return d[0] + "-label-txt"; })
      .attr("class", "rel-dist-label")
      .attr("x", 0)
      .attr("y", 0)
      .text(function(d) { return d[1]; })
      .attr("transform", get_dm_label_transform);

    rel_dist_masks.transition().duration(dt)
        .select(".rel-dist-label")
      .attr("transform", get_dm_label_transform);

    // Stroke reliable distance labels
    var rel_dist_stroke = d3.select("#reliable-dist-group")
      .selectAll(".rel-dist-label-stroke").data(dm_label_data);

    // console.log()
    rel_dist_stroke.enter()
      .append("text")
        .attr("class", "rel-dist-label rel-dist-label-stroke")
        .attr("id", function(d) { return d[0] + "-label-stroke"; })
        .attr("x", 0)
        .attr("y", 0)
        .attr("transform", get_dm_label_transform)
        .text(function(d) { return d[1]; });

    rel_dist_stroke.transition().duration(dt)
      .attr("transform", get_dm_label_transform);

    // Convergence flag
    d3.select("#plot-main-group")
      .classed("non-converged", !query_data.converged);

    var convergence_warning = d3.selectAll("#plot-main-group")
      .selectAll("#convergence-warning").data([null]);

    convergence_warning.enter()
      .append("text")
        .attr("id", "convergence-warning")
        .attr("transform", "translate(-8, -12)")
        .text("Fit did not converge!");

    d3.select("#convergence-warning")
      .attr("x", margins.left + plot_width)
      .attr("y", margins.top + plot_height);

    // convergence_warning.exit().remove();

    // No data
    d3.select("#plot-main-group")
      .classed("no-data", !query_data.success);

    // DM, reddening indicator
    // var reddening_focus = svg.select("#plot-area")
    //   .selectAll("#reddening-focus").data([null])
    //     .enter()
    var reddening_focus = plot_area_group.append("g")
      .attr("id", "reddening-focus")
      .attr("class", "no-display");
      // .attr("transform",
      //   "translate(" + margins.left + "," + margins.top + ")"
      // );

    // Lines indicating reddening at x-position of mouse on plot
    reddening_focus.append("line")
      .attr("id", "plot-x-indicator")
      .attr("class", "plot-indicator");

    reddening_focus.append("line")
      .attr("id", "plot-y-indicator")
      .attr("class", "plot-indicator");

    reddening_focus.append("rect")
      .attr("id", "plot-y-spread-indicator");

    // Label displaying reddening at x-position of mouse
    var focus_label_gp = reddening_focus.append("g")
      .attr("id", "plot-focus-label")
      .attr("transform",
        "translate(" +
        (0.02*plot_width) + "," +
        (0.02*plot_width) + ")"
      );

    var focus_label = focus_label_gp.append("text")
      .attr("dominant-baseline", "hanging");

    focus_label.append("tspan")
      .text("d = ");
    focus_label.append("tspan")
      .attr("id", "mouse-kpc")
      .text("1.5");
    focus_label.append("tspan")
      .text(" kpc");

    focus_label.append("tspan")
      .attr("x", 0)
      .attr("dy", "1.2em")
      .text("E(B-V) = ");

    focus_label.append("tspan")
      .attr("id", "mouse-reddening")
      .text("3.0");

    focus_label.append("tspan")
      .attr("id", "mouse-reddening-plus")
      .attr("dx", "0.2em")
      .attr("dy", "-0.4em")
      .attr("font-size", "65%")
      .text("+0.5");

    focus_label.append("tspan")
      .attr("id", "mouse-reddening-minus")
      .attr("dy", "+1.2em")
      .attr("font-size", "65%")
      .text("-0.5");

    // Update reddening label on mouse move
    var mouse_move = function(obj) {
      var x_mouse = d3.mouse(obj)[0];
      var dm_mouse = scale_x.invert(x_mouse);
      var bin_high = d3.bisectLeft(query_data.distmod, dm_mouse);

      var dm_high = query_data.distmod[bin_high];
      var dm_low = query_data.distmod[bin_high-1];
      var a = (dm_high - dm_mouse) / (dm_high - dm_low);

      // Calculate samples of reddening at this distance
      var reddening_samp = query_data.samples.map(function(row) {
        return a * row[bin_high-1] + (1. - a) * row[bin_high];
      }).sort(d3.ascending);

      // Calculate percentiles of reddening at this distance
      var reddening_low = d3.quantile(reddening_samp, 0.1587);
      var reddening_med = d3.median(reddening_samp);
      var reddening_high = d3.quantile(reddening_samp, 0.8413);

      // Calculate how much to inflate uncertainty
      var sigma = 0.5 * (reddening_high - reddening_low);
      var sigma_floor = 0.03;
      var delta_sigma = (
        Math.sqrt(sigma*sigma + sigma_floor*sigma_floor)
        - sigma
      );

      // Inflate uncertainty evenly on upper and lower end
      reddening_low = d3.max([0, reddening_low - 0.5*delta_sigma]);
      reddening_high = reddening_high + 0.5*delta_sigma;

      d3.select("#plot-x-indicator")
        .attr("x1", x_mouse)
        .attr("x2", x_mouse)
        .attr("y1", scale_y(0))
        .attr("y2", scale_y(reddening_med));

      d3.select("#plot-y-indicator")
        .attr("x1", 0)
        .attr("x2", x_mouse)
        .attr("y1", scale_y(reddening_med))
        .attr("y2", scale_y(reddening_med));

      d3.select("#plot-y-spread-indicator")
        .attr("x", 0)
        .attr("y", scale_y(reddening_high))
        .attr("width", x_mouse)
        .attr("height", scale_y(reddening_low) - scale_y(reddening_high));

      var kpc_mouse = Math.pow(10, dm_mouse/5.0 - 2.0);

      d3.select("#mouse-kpc")
        .text(d3.format(".2f")(kpc_mouse));

      d3.select("#mouse-reddening")
        .text(d3.format(".2f")(reddening_med));

      d3.select("#mouse-reddening-plus")
        .text("+" + d3.format(".2f")(reddening_high - reddening_med));

      var plus_label_length = d3.select("#mouse-reddening-plus")
        .node().getComputedTextLength();

      d3.select("#mouse-reddening-minus")
        .attr("dx", "-" + plus_label_length)
        .text("-" + d3.format(".2f")(reddening_med - reddening_low));
    };

    // Mouse overlay (must be last element in SVG, so on top)
    var overlay = svg.selectAll("#plot-mouse-overlay").data([null]);

    overlay.enter()
      .append("rect")
      .attr("id", "plot-mouse-overlay");

    svg.select("#plot-mouse-overlay")
      .attr("width", plot_width)
      .attr("height", plot_height)
      .attr("transform",
        "translate(" + margins.left + "," + margins.top + ")"
      )
      .on("mouseover", function() {
        d3.select("#reddening-focus")
          .classed("no-display", false);
      })
      .on("mouseout", function() {
        d3.select("#reddening-focus")
          .classed("no-display", true);
      })
      .on("mousemove", function() { return mouse_move(this); });
  };

  /*
   * Postage stamps
   */

  var show_image_div = function(callback) {
    if (callback) {
      $("#download-div").on("shown.bs.collapse", function() {
        callback();
      });
    }
    $("#postage-stamp-div").on("shown.bs.collapse", function() {
      $("#download-div").collapse("show");
    });
    $("#postage-stamp-div").collapse("show");
  };

  var place_images = function(data) {
    $("#postage-stamp-1").attr("src", data.image1);
    $("#postage-stamp-2").attr("src", data.image2);
    $("#postage-stamp-3").attr("src", data.image3);
    $("#ps-label-1").text(data.label1);
    $("#ps-label-2").text(data.label2);
    $("#ps-label-3").text(data.label3);
  };

  var update_ps_dimensions = function() {
    console.log("Resizing postage-stamp overlays.");
    var img_dim = utils.get_obj_dimensions(
      d3.select(".ps-img").node()
    );
    d3.selectAll(".ps-overlay")
      .attr("width", img_dim.width + "px")
      .attr("height", img_dim.height + "px")
      .style("left", img_dim.left + "px")
      .style("top", img_dim.top + "px");
  };

  var get_ps_lb = function(obj, query_data) {
    // var obj_dim = utils.get_obj_dimensions(obj);
    var x_max_proj = astrocoords.proj_gnomonic(
      astrocoords.deg2rad(query_data.radius),
      0, 0, 1, 0
    ).x;
    var mouse_xy = d3.mouse(obj);
    var lon0 = astrocoords.deg2rad(query_data.l),
        lat0 = astrocoords.deg2rad(query_data.b);
    var width = d3.select(obj).attr("width");

    var x = -2 * (mouse_xy[0] / width - 0.5) * x_max_proj;
    var y = -2 * (mouse_xy[1] / width - 0.5) * x_max_proj;

    // console.log(
    //   "(x, y) = ("
    //   + d3.format(".4f")(x)
    //   + ", "
    //   + d3.format(".4f")(y)
    //   + ")"
    // );
    // console.log("x_max_proj = " + x_max_proj);
    // console.log("mouse_xy = " + mouse_xy);
    // console.log("obj_dim:");
    // console.log(obj_dim);

    var coords = astrocoords.proj_gnomonic_inv(
      x, y, lon0, Math.cos(lat0), Math.sin(lat0)
    );

    return {
      "l": astrocoords.rad2deg(coords.lon),
      "b": astrocoords.rad2deg(coords.lat)
    };
  };

  // Gets coordinates when user clicks on postage stamp,
  // and converts to whatever coordinate system the toggle
  // indicates.
  var get_ps_coords = function(obj, query_data) {
    var coords_gal = get_ps_lb(obj, query_data);
    var target_coord_sys = get_coord_sys();
    var coords = convert_coord_sys(
      package_gal_coords(coords_gal),
      target_coord_sys
    );
    return coords;
  }

  var set_ps_labels = function(coords) {
    if (coords.coord_sys === "equ") {
      d3.selectAll(".ps-focus-gal")
        .classed("no-display", true);
      d3.selectAll(".ps-focus-equ")
        .classed("no-display", false);
      var fmt = d3.format("02d");
      var hms = astrocoords.deg2hms(coords.lon.val);
      d3.selectAll(".RA-hh")
        .text(fmt(hms.h));
      d3.selectAll(".RA-mm")
        .text(fmt(hms.m));
      d3.selectAll(".RA-ss")
        .text(fmt(hms.s));
      d3.selectAll(".Dec-deg")
        .text(d3.format(".2f")(coords.lat.val));
    } else if (coords.coord_sys === "gal" ){
      d3.selectAll(".ps-focus-equ")
        .classed("no-display", true);
      d3.selectAll(".ps-focus-gal")
        .classed("no-display", false);
      var fmt = d3.format(".2f");
      d3.selectAll(".gal-l-deg")
        .text(fmt(coords.lon.val));
      d3.selectAll(".gal-b-deg")
        .text(fmt(coords.lat.val));
    } else {
      console.log("set_ps_labels: Invalid coordsys:");
      console.log(coords.coord_sys);
    }
  };

  // var set_ps_labels_gal = function(coords_gal) {
  //   d3.selectAll(".ps-focus-equ")
  //     .classed("no-display", true);
  //   d3.selectAll(".ps-focus-gal")
  //     .classed("no-display", false);
  //   var fmt = d3.format(".2f");
  //   d3.selectAll(".gal-l-deg")
  //     .text(fmt(coords_gal.l));
  //   d3.selectAll(".gal-b-deg")
  //     .text(fmt(coords_gal.b));
  // };
  //
  // var set_ps_labels_equ = function(coords_equ) {
  //   d3.selectAll(".ps-focus-gal")
  //     .classed("no-display", true);
  //   d3.selectAll(".ps-focus-equ")
  //     .classed("no-display", false);
  //   var fmt = d3.format("02d");
  //   var hms = astrocoords.deg2hms(coords_equ.a);
  //   d3.selectAll(".RA-hh")
  //     .text(fmt(hms.h));
  //   d3.selectAll(".RA-mm")
  //     .text(fmt(hms.m));
  //   d3.selectAll(".RA-ss")
  //     .text(fmt(hms.s));
  //   d3.selectAll(".Dec-deg")
  //     .text(d3.format(".2f")(coords_equ.d));
  // };

  // var set_ps_labels = function(coords_gal) {
  //   var coord_sys = get_coord_sys();
  //   if(coord_sys === "gal") {
  //     set_ps_labels_gal(coords_gal);
  //   } else if (coord_sys === "equ") {
  //     var coords_equ = astrocoords.gal2equ_J2000(
  //       coords_gal.l,
  //       coords_gal.b
  //     );
  //     set_ps_labels_equ(coords_equ);
  //   }
  // };

  /*
   * Update UI elements
   */

  var coords2qstring = function(coords) {
    var qstring = "?lon=" + coords.lon.val +
                  "&lat=" + coords.lat.val +
                  "&coordsys=" + coords.coord_sys;
    return qstring;
  };

  // Update button to access ASCII table
  var update_table_btn = function(coords) {
    var href = "/api/v2/interactive/bayestar2015/lostable"
               + coords2qstring(coords);
    d3.select("#table-btn")
      .attr("href", href)
      .classed("disabled", false);
  };

  var disable_table_btn = function() {
    d3.select("#table-btn")
      .attr("href", "#")
      .classed("disabled", false);
  };

  // Converts coordinates to the specified target coordinate system.
  var convert_coord_sys = function(coords, target_coord_sys) {
    if (coords.coord_sys === target_coord_sys) {
      return coords;
    }
    if ((coords.coord_sys === "gal")
     && (target_coord_sys === "equ")) {
      var c_target = astrocoords.gal2equ_J2000(
        coords.lon.val,
        coords.lat.val
      );
      return package_equ_coords(c_target);
    } else if ((coords.coord_sys === "equ")
            && (target_coord_sys === "gal")) {
      var c_target = astrocoords.equ2gal_J2000(
        coords.lon.val,
        coords.lat.val
      );
      return package_gal_coords(c_target);
    }
    return null; // Something wrong with either coords.coord_sys or
                 // target_coord_sys.
  };

  // Sets lon/lat input boxes to the specified coordinates, and flips
  // the coordinate system toggle to the correct setting.
  var update_input_boxes = function(coords, preserve_coordsys_toggle) {
    var do_update = function(c) {
      $('input[name="gal-l"]').val(c.lon.val);
      $('input[name="gal-b"]').val(c.lat.val);
      if (c.coord_sys === "gal") {
        $("#coord-toggle").bootstrapToggle("on");
      } else if (c.coord_sys === "equ") {
        $("#coord-toggle").bootstrapToggle("off");
      }
    };

    if (preserve_coordsys_toggle) { // Do not flip the coordsys toggle
      console.log("Preserving coordsys toggle.");
      var target_coord_sys = get_coord_sys();
      console.log("Target coordsys: " + target_coord_sys);
      var c = convert_coord_sys(coords, target_coord_sys);
      console.log("Setting input boxes to:");
      console.log(c);
      do_update(c);
    } else {  // Flip the coordsys toggle to whatever is in "coords"
      do_update(coords);
    }
  };

  // Sets the URL query string to represent the given coordinates.
  var set_qstring = function(coords) {
    var qstring = coords2qstring(coords);
    console.log(qstring);
    window.history.pushState("", "", qstring);
  };

  /*
   * Query server
   */

  var query_server = function(coords, f_success, f_error) {
    $.ajax({
      type: "GET",
      url: "/gal-lb-query",
      data: {
        "lon": coords.lon.val,
        "lat": coords.lat.val,
        "coordsys": coords.coord_sys
      },
      dataType: "json",
      success: function(data) {
        console.log("Data received:");
        console.log(data);
        f_success(data);
      },
      error: function(xhr, status, err) {
        console.log("Error.");
        console.log('Message from server: ' + xhr.responseText);
        f_error(xhr, status, err);
      }
    });
  };

  /*
   * Full update methods (click query, click postage stamp)
   */

  var package_gal_coords = function(coords_gal) {
    return {
      "lon": {
        "val": coords_gal.l,
        "format": "deg"
      },
      "lat": {
        "val": coords_gal.b,
        "format": "deg"
      },
      "coord_sys": "gal"
    };
  };

  var package_equ_coords = function(coords_equ) {
    return {
      "lon": {
        "val": coords_equ.a,
        "format": "deg"
      },
      "lat": {
        "val": coords_equ.d,
        "format": "deg"
      },
      "coord_sys": "equ"
    };
  };

  var update_full = function(coords) {
    console.log("update_full");

    // Animate query button
    $("#submit-btn-icon").attr(
      "class",
      "fa fa-spinner fa-spin fa-lg"
    );

    // On query success
    var success = function(data) {
      // Update the URL query string
      set_qstring(coords);

      // Update link to ASCII table
      update_table_btn(coords);

      // Hide any custom message
      hide_custom_alert(); // TODO: Create special warning div for this

      // Update line plot
      show_plot_div(function() {
        console.log("shown");
        plot_distance_reddening(data);
      });

      // Set the images
      place_images(data);
      show_image_div(update_ps_dimensions);

      // Reset the query button
      $("#submit-btn-icon").attr(
        "class",
        "glyphicon glyphicon-search"
      );

      // Hide the "Enter query coords" message
      $("#enter-coords-alert").alert("close");

      // Mouse over postage stamp
      d3.selectAll(".overlay").on("mousemove", function() {
        var coords = get_ps_coords(this, data);
        set_ps_labels(coords);
      });

      // Click on postage stamp
      d3.selectAll(".overlay").on("click", function() {
        console.log("clicked");
        var coords = get_ps_coords(this, data);
        console.log(coords);
        // var coords = package_gal_coords(coords_gal);
        update_input_boxes(coords);//, true);
        update_full(coords);
      });
    }

    var error = function(xhr, status, err) {
      // Reset the query button
      $("#submit-btn-icon").attr(
        "class",
        "glyphicon glyphicon-search"
      );

      disable_table_btn();

      show_custom_alert("Query failed."); // TODO: Create special warning div for this
    };

    // Get data from server
    console.log("querying");
    query_server(coords, success, error);
  };

  var update_from_submit = function() {
    // Get coordinates
    var coords = get_coordinates();
    console.log(coords);
    if(!issue_coord_warnings(coords)) { return; }

    update_full(coords);
  };

  // Converts the query string into coordinates.
  // Returns null if query string is invalid.
  var get_coords_from_qstring = function() {
    var url_params = new URLSearchParams(window.location.search);

    var expected_keys = {
      "lon": "lon",
      "lat": "lat",
      "coordsys": "coord_sys"
    };
    var coords = {};

    for (var key in expected_keys) {
      if (!url_params.has(key)) { return null; }
      coords[expected_keys[key]] = url_params.get(key);
      console.log(key + " = " + url_params.get(key));
    }

    console.log(coords);

    if((coords["coord_sys"] !== "gal")
       && (coords["coord_sys"] !== "equ")) {
      return null;
    }
    var lon = astrocoords.parse_angle(coords["lon"], true);
    var lat = astrocoords.parse_angle(coords["lat"], false);

    // if ((lon === null) || (lat === null)) {
    //   return null;
    // }

    return {
      "lon": lon,
      "lat": lat,
      "coord_sys": coords["coord_sys"]
    };
    // if(urlParams.has("lon") && urlParams.has("lat") && urlParams.has("coordsys")) {
    //
    // }
  };

  var update_from_qstring = function() {
    // Get coordinates
    var coords = get_coords_from_qstring();
    console.log(coords);
    if (!coords) { return; }
    update_input_boxes(coords);
    if(!issue_coord_warnings(coords)) { return; }

    update_full(coords);
  };


  /*
   * User event listeners
   */

  // Submit query
  $("#submit-btn").click(function() { update_from_submit(); });
  var submit_if_enter = function(e) {
    var key = e.which;
    if (key == 13) { update_from_submit(); }
  };
  $("#gal-l-input").keypress(submit_if_enter);
  $("#gal-b-input").keypress(submit_if_enter);

  // Toggle coordinates
  $("#coord-toggle").change(function() {
    if($(this).prop("checked")) {
      set_coordsys("gal");
    } else {
      set_coordsys("equ");
    }
  });
  $("#coord-toggle").bootstrapToggle("on");

  // Window resize
  $(window).resize(utils.debounce(update_ps_dimensions, 250));

  // Mouse over postage stamp
  d3.selectAll(".overlay").on("mouseover", function() {
    // console.log(this.parentNode);
    d3.select(this.parentNode).select(".ps-focus")
      .classed("no-display", false);
  });
  d3.selectAll(".overlay").on("mouseout", function() {
    // console.log(this.parentNode);
    d3.select(this.parentNode).select(".ps-focus")
      .classed("no-display", true);
  });

  // Execute query from query string
  update_from_qstring();
}

$(document).ready(function() { create_plot(); });

})();
