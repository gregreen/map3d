$(document).ready(function() {
  
  useGalactic = true;
  
  // Coordinate toggle
  $('#coord-toggle').change(function() {
    if ($(this).prop("checked")) {
      useGalactic = true;
      d3.select("#gal-l-input").attr("placeholder", "lon. (\u00B0)");
      d3.select("#gal-b-input").attr("placeholder", "lat. (\u00B0)");
      d3.select("#gal-l-symbol").text("\u2113");
      d3.select("#gal-b-symbol").text("b");
      d3.select("#submit-btn").classed("btn-success", true);
      d3.select("#submit-btn").classed("btn-primary", false);
    } else {
      useGalactic = false;
      d3.select("#gal-l-input").attr("placeholder", "R.A. (\u00B0)");
      d3.select("#gal-b-input").attr("placeholder", "Dec. (\u00B0)");
      d3.select("#gal-l-symbol").text("\u03B1");
      d3.select("#gal-b-symbol").text("\u03B4");
      d3.select("#submit-btn").classed("btn-success", false);
      d3.select("#submit-btn").classed("btn-primary", true);
    }
  });
  
  // Alerts
  function showBadCoordsAlert() {
    if (d3.select("#bad-coords-div").classed("collapse in")) {
      return;
    }
    $("#bad-coords-div").collapse("show")
    d3.select("#bad-coords-div")
      .transition().duration(200)
      .style("opacity", 1);
  }
  
  function hideBadCoordsAlert() {
    if (!d3.select("#bad-coords-div").classed("collapse in")) {
      return;
    }
    $("#bad-coords-div").collapse("hide");
    d3.select("#bad-coords-div")
      .transition().duration(200)
      .style("opacity", 0);
  }
  
  function showCustomAlert(msg) {
    var alertDiv = d3.select("#custom-alert-div");
    var prevMsg = alertDiv.select("h4").text();
    
    var execShow = function() {
      alertDiv.select("h4").text(msg);
      $("#custom-alert-div").collapse("show")
      alertDiv.transition().duration(200)
        .style("opacity", 1);
    };
    
    if (d3.select("#custom-alert-div").classed("collapse in")) {
      if (prevMsg == msg) {
        return;
      } else {
        $("#custom-alert-div").on("hidden.bs.collapse", function() {
          execShow();
        });
        $("#custom-alert-div").collapse("hide");
      }
    } else {
      execShow();
    }
  }
  
  function hideCustomAlert() {
    if (!d3.select("#custom-alert-div").classed("collapse in")) {
      return;
    }
    $("#custom-alert-div").collapse("hide");
    d3.select("#custom-alert-div")
      .transition().duration(200)
      .style("opacity", 0);
  }
  
  // D3 Plots
  
  function packData(xVals, yData) {
    return d3.range(yData.length).map( function(idx) {
      return d3.zip(xVals, yData[idx]);
    });
  };
  
  function drawPlotSafe(forceUncollapse, container, dt, xVals, yBest, ySamples, conv, noData) {
    var linePlotDiv = d3.select("#line-plot-div");
    
    if (linePlotDiv.classed("collapse in")) {
      drawPlot(container, dt, xVals, yBest, ySamples, conv, noData);
    } else if(forceUncollapse) {
      $(linePlotDiv[0][0]).on("shown.bs.collapse", function() {
        drawPlot(container, dt, xVals, yBest, ySamples, conv, noData);
        
        $("#postage-stamp-div").on("shown.bs.collapse", function() {
          drawPSOverlays();
          
          $("#download-div").collapse("show");
        });
        
        $("#postage-stamp-div").collapse("show");
      });
      
      $(linePlotDiv[0][0]).collapse("show");
    }
  }
  
  function drawPlot(container, dt, xVals, yBest, ySamples, conv, noData) {
    if (!d3.select("#line-plot-div").classed("collapse in")) {
      return;
    }
    
    var fullwidth = $(container).width(),
        fullheight = $(container).height();
    
    var naiveScaling = fullwidth/600;
    
    scaling = d3.max([0.5, fullwidth/600]);
    scaling = d3.min([2, scaling]);
    
    console.log("scaling: " + scaling);
    
    labelsize = 14 * scaling;
    ticksize = 12 * scaling;
    
    var margins = {left:70*scaling, right:20*scaling,
                   bottom:80*scaling, top:20*scaling};
    
    var width = fullwidth - margins.left - margins.right,
        height = fullheight - margins.bottom - margins.top;
    
    x = d3.scale.linear()
      .domain(d3.extent(xVals))
      .range([0, width]);
    
    yMax = d3.max(ySamples, function(a) { return d3.max(a); });
    
    y = d3.scale.linear()
      .domain([0, 1.1*yMax])
      .range([height, 0]);
    
    var line = d3.svg.line()
      .x(function(d) { return x(d[0]); })
      .y(function(d) { return y(d[1]); });
    
    var xAxis = d3.svg.axis()
      .scale(x)
      .orient("bottom");
    
    var yAxis = d3.svg.axis()
      .scale(y)
      .orient("left")
      .ticks(6);
    
    // SVG Canvas
    if (d3.select(container).selectAll("svg")[0].length < 1) {
      svg = d3.select(container).append("svg")
        .append("g")
          .attr("id", "main-group");
      
      lineGroup = svg.append("g")
        .attr("id", "DM-EBV-lines");
      
      svg.append("g")
        .attr("class", "toggle-converged")
        .style("opacity", 0)
        .append("text")
          .attr("id", "convergence-warning")
          .style("text-anchor", "end")
          .style("font-family", "Cutive Mono")
          .style("fill", "red")
          .text("non-converged!");
      
      svg.append("g")
        .attr("class", "nodata-on")
        .style("opacity", 0)
        .append("text")
          .attr("id", "nodata-indicator")
          .style("text-anchor", "middle")
          .style("font-family", "Cutive Mono")
          .style("fill", "steelblue")
          .style("opacity", 0.5)
          .text("No Data");
    }
    
    d3.select(container).select("svg")
      .attr("width", fullwidth)
      .attr("height", fullheight)
      .attr("viewBox", "0 0 " + fullwidth + " " + fullheight);
    
    d3.select("#main-group")
      .attr("transform", "translate(" + margins.left + "," + margins.top + ")");
    
    d3.select("#convergence-warning")
      .transition().duration(dt)
      .attr("x", x(xVals[xVals.length-1]))
      .attr("y", height)
      .attr("dy", (-1*ticksize) + "pt")
      .style("font-size", ticksize + "pt");
    
    d3.select("#nodata-indicator")
      .transition().duration(dt)
      .attr("x", 0.5*width)
      .attr("y", 0.5*height)
      .attr("dy", (-0.5*ticksize) + "pt")
      .style("font-size", (3*ticksize) + "pt");
    
    // x-Axis
    if (svg.selectAll(".x.axis")[0].length < 1) {
      svg.append("g")
        .attr("class", "x axis")
        .attr("transform", "translate(0," + height + ")")
        .call(xAxis)
      .append("text")
        .attr("id", "xlabel")
        .attr("x", width/2)
        .attr("dy", (3*ticksize) + "pt")
        .text("Distance Modulus (mags)")
        .style("text-anchor", "middle");
    } else {
      svg.selectAll(".x.axis")
        .attr("transform", "translate(0," + height + ")")
        .transition(dt).duration(dt)
        .call(xAxis);
      
      d3.select("#xlabel")
        .attr("x", width/2)
        .attr("dy", (3*ticksize) + "pt");
    }
    
    // y-Axis
    if (svg.selectAll(".y.axis")[0].length < 1) {
      svg.append("g")
        .attr("class", "y axis")
        .call(yAxis)
      .append("text")
        .attr("id", "ylabel")
        .attr("transform", "rotate(-90)")
        .attr("y", 0)
        .attr("x", -height/2)
        .attr("dy", (-3*ticksize) + "pt")
        .style("text-anchor", "middle")
        .text("E(B-V) (mags)");
    } else {
      svg.selectAll(".y.axis")
        .transition().duration(dt)
        .call(yAxis);
      
      d3.select("#ylabel")
        .attr("x", -height/2)
        .attr("dy", (-3*ticksize) + "pt");
    }
    
    // Fonts
    d3.selectAll(".tick > text")
      .style("font-size", ticksize + "pt")
      .style("font-family", "Lora");
    
    d3.selectAll(".axis > text")
      .style("font-size", labelsize + "pt")
      .style("font-family", "Lora");
    
    // Change plot appearance based on (non-)convergence
    if (conv == 0) {
      lineColor = "red";
      
      d3.selectAll(".toggle-converged")
        .transition().duration(dt)
        .style("opacity", 1);
    } else {
      lineColor = "steelblue";
      
      d3.selectAll(".toggle-converged")
        .transition().duration(dt)
        .style("opacity", 0);
    }
    
    // Indicate absence of data
    if (noData == 1) {
      d3.selectAll(".nodata-on")
        .transition().duration(dt)
        .style("opacity", 1);
      d3.selectAll(".nodata-off")
        .transition().duration(dt)
        .style("opacity", 0);
    } else {
      d3.selectAll(".nodata-on")
        .transition().duration(dt)
        .style("opacity", 0);
      d3.selectAll(".nodata-off")
        .transition().duration(dt)
        .style("opacity", 1);
    }
    
    // Best Line
    bestData = [d3.zip(xVals, yBest)];
    
    var lines = lineGroup.selectAll("#best").data(bestData).attr("class", "line");
    
    // transition from previous paths to new paths
    lines.transition().duration(dt)
      .attr("stroke", lineColor)
      .attr("d", line);
    
    // enter any new data
    lines.enter()
      .append("path")
      .attr("id", "best")
      .attr("class", "line")
      .attr("d", line)
      .attr("stroke", lineColor)
      .attr("stroke-width", "2.5px");
    
    // exit
    lines.exit()
      .remove();
    
    // Samples
    sampleData = packData(xVals, ySamples);
    
    var lines = lineGroup.selectAll("#samples").data(sampleData).attr("class", "line");
    
    // transition from previous paths to new paths
    lines.transition().duration(dt)
      .attr("stroke", lineColor)
      .attr("d", line);
    
    // enter any new data
    lines.enter()
      .append("path")
      .attr("id", "samples")
      .attr("class", "line")
      .attr("d", line)
      .attr("opacity", 0.2)
      .attr("stroke", lineColor)
      .attr("stroke-width", "1.5px");
    
    // exit
    lines.exit()
      .remove();
    
    
    /*
     * Legend
     */
    
    var xLegendStart = 15.5;
    var xLegend = d3.range(0., 1.251, 0.25)
      .map(function(a) { return xLegendStart + a; });
    var yLegendBest =     [ 0.70,  0.75,  0.75,   0.85,  1.00, 1.00];
    var yLegendSamples = [[ 0.10,  0.10,  0.15,   0.20,  0.25, 0.25],
                          [ 0.20,  0.25,  0.25,   0.30,  0.35, 0.35],
                          [ 0.00,  0.05,  0.30,   0.35,  0.40, 0.40]];
    var yMinLegend = 0.25 * yMax;
    var yMaxLegend = 0.45 * yMax;
    var kLegendLast = xLegend.length-1;
    
    var yScaleLegend = d3.scale.linear()
      .domain([0, 1])
      .range([yMinLegend, yMaxLegend]);
    //function(a) { return yMinLegend + (yMaxLegend-yMinLegend)*a; };
    
    if (d3.select("#main-group").selectAll("#legend-wrapper")[0].length < 1) {
      var legendWrapper = d3.select("#main-group").append("g")
        .attr("id", "legend-wrapper")
        //.style("display", "none")
        .attr("class", "nodata-off");
      
      var legend = legendWrapper.append("g")
        .attr("id", "legend");
      
      legendWrapper.append("rect")
        .attr("id", "legend-frame")
        .style("fill", "black")
        .style("fill-opacity", 0.01)
        .style("stroke", "black")
        .style("stroke-width", "1pt")
        .style("stroke-opacity", 0.05);
      
      legend.append("text")
        .attr("id", "legend-best-label")
        .style("text-anchor", "start")
        .style("font-family", "Cutive Mono")
        .style("fill", "steelblue")
        .style("opacity", 1)
        .text("best fit");
      
      legend.append("text")
        .attr("id", "legend-sample-label")
          .style("text-anchor", "start")
          .style("font-family", "Cutive Mono")
          .style("fill", "steelblue")
          .style("opacity", 1)
          .text("samples");
    }
    
    var legendMargins = {"x": 5, "y": 5};
    
    var h0 = (y(yMinLegend) - y(yMaxLegend));
    var labelFrameWidth = 1.7 * (scaling / naiveScaling);
    labelFrameWidth = (1+labelFrameWidth) * (x(xLegend[kLegendLast])-x(xLegend[0]));
    labelFrameWidth += 2*legendMargins.y;
    var xOffsetLabel = x(xVals[xVals.length-1]) - (x(xLegend[0]) + labelFrameWidth);
    
    var legendBounds = {
      "x": x(xLegend[0]) + xOffsetLabel,
      "y": y(yMaxLegend)-0.1*h0,
      "width": labelFrameWidth,
      "height": 1.1*h0 + 2*legendMargins.y
    };
    
    d3.select("#legend-frame")
      .transition().duration(dt)
      .attr("x", (legendBounds.x - legendMargins.x) + "px")
      .attr("y", (legendBounds.y - legendMargins.y) + "px")
      .attr("width", legendBounds.width + "px")
      .attr("height", legendBounds.height + "px");
    
    d3.select("#legend-best-label")
      .transition().duration(dt)
      .attr("x", x(xLegend[kLegendLast]+0.25) + xOffsetLabel)
      .attr("y", y(yScaleLegend(yLegendBest[kLegendLast])))
      .attr("dy", (0.25*0.8*ticksize) + "pt")
      .style("font-size", (0.8*ticksize) + "pt")
      .style("fill", lineColor);
    
    d3.select("#legend-sample-label")
      .transition().duration(dt)
      .attr("x", x(xLegend[kLegendLast]+0.25) + xOffsetLabel)
      .attr("y", y(yScaleLegend(0.325)))
      .attr("dy", (0.25*0.8*ticksize) + "pt")
      .style("font-size", (0.8*ticksize) + "pt")
      .style("fill", lineColor);
    
    //d3.select("#legend-wrapper")
    //  .style("display", null);
    
    xLegend = xLegend.map(function(a) {
      return a + x.invert(xOffsetLabel) - x.invert(0);
    });
    
    var legendBestData = [d3.zip(xLegend, yLegendBest.map(yScaleLegend))];
    
    var linesLegendBest = d3.select("#legend").selectAll("#legend-line-best")
      .data(legendBestData)
      .attr("class", "line");
    
    linesLegendBest.transition().duration(dt)
      .attr("stroke", lineColor)
      .attr("d", line)
      .attr("stroke-width", "2.5px");
    
    linesLegendBest.enter()
      .append("path")
      .attr("id", "legend-line-best")
      .attr("class", "line")
      .attr("d", line)
      .attr("stroke", lineColor)
      .attr("stroke-width", "2.5px");
    
    linesLegendBest.exit()
      .remove();
    
    var yLegendSamplesScaled = yLegendSamples.map(function(a) { return a.map(yScaleLegend); });
    
    var legendSampleData = packData(xLegend, yLegendSamplesScaled);
    
    var linesLegendSamples = d3.select("#legend").selectAll("#legend-line-samples")
      .data(legendSampleData)
      .attr("class", "line");
    
    linesLegendSamples.transition().duration(dt)
      .attr("stroke", lineColor)
      .attr("d", line)
      .attr("stroke-width", "1.5px");
    
    linesLegendSamples.enter()
      .append("path")
      .attr("id", "legend-line-samples")
      .attr("class", "line")
      .attr("d", line)
      .attr("opacity", 0.2)
      .attr("stroke", lineColor)
      .attr("stroke-width", "1.5px");
    
    linesLegendSamples.exit()
      .remove();
    
    /*
     *  Mouseover
     */
    
    var pmScale = 0.7;
    
    if (svg.selectAll("#focus")[0].length < 1) {
      focus = svg.append("g")
        .attr("id", "focus")
        .attr("display", "none");
      
      svg.append("rect")
        .attr("id", "mouse-overlay")
        .attr("class", "overlay")
        .attr("width", width)
        .attr("height", height)
        .on("mouseover", function() { d3.select("#focus").attr("display", null); })
        .on("mouseout", function() { d3.select("#focus").attr("display", "none"); })
        .on("mousemove", mouseMove);
      
      focus.append("line")
        .attr("id", "x-indicator")
        .attr("x1", 0)
        .attr("x2", 0)
        .attr("y1", 0)
        .attr("y2", height)
        .attr("stroke", "black")
        .attr("stroke-width", "2px")
        .attr("opacity", 0.15);
      
      focus.append("line")
        .attr("id", "y-indicator")
        .attr("x1", 0)
        .attr("x2", width)
        .attr("y1", 0)
        .attr("y2", 0)
        .attr("stroke", "black")
        .attr("stroke-width", "2px")
        .attr("opacity", 0.15);
      
      focus.append("rect")
        .attr("id", "y-spread-indicator")
        .attr("fill", "black")
        .attr("fill-opacity", 0.05);
      
      txtEl = focus.append("text")
        .attr("id", "text-indicator")
        .attr("x", 0)
        .attr("y", 0)
        .style("text-anchor", "start")
        .style("font-size", ticksize + "pt")
        .style("font-family", "Cutive Mono")
        .style("fill", "steelblue")
        .style("opacity", 0.75);
      
      txtEl.append("tspan")
        .attr("id", "dist-label")
        .attr("x", 0.8*ticksize + "pt");
      
      txtEl.append("tspan")
        .attr("id", "EBV-label")
        .attr("x", 0.8*ticksize + "pt")
        .attr("dy", ticksize + "pt");
      
      txtEl.append("tspan")
        .attr("id", "EBV-plus")
        .attr("dx", 0.25*ticksize + "pt")
        .attr("dy", -pmScale*ticksize + "pt");
      
      txtEl.append("tspan")
        .attr("id", "EBV-minus")
        .attr("dy", pmScale*ticksize + "pt");
    } else {
      d3.select("#mouse-overlay")
        .attr("width", width)
        .attr("height", height);
      
      d3.select("#focus")
        .attr("display", "none");
      
      d3.select("#dist-label")
        .attr("x", 0.8*ticksize + "pt");
      
      d3.select("#EBV-label")
        .attr("x", 0.8*ticksize + "pt")
        .attr("dy", ticksize + "pt");
    }
    
    d3.select("#EBV-plus")
      .attr("dx", 0.25*ticksize + "pt")
      .attr("dy", -0.65*pmScale*ticksize + "pt")
      .style("font-size", pmScale*ticksize + "pt");
    
    d3.select("#EBV-minus")
      .attr("dx", -3*pmScale*ticksize + "pt")
      .attr("dy", pmScale*ticksize + "pt")
      .style("font-size", pmScale*ticksize + "pt");
    
    d3.select("#text-indicator")
      .transition().duration(dt)
      .attr("x", 0.025*width)
      .attr("y", 0.015*height)
      .style("font-size", ticksize + "pt")
      .attr("dy", 0.5*ticksize + "pt");
    
    var bisect_x = d3.bisector(function(d) { return d; }).left;
    var text_formatter = d3.format(".2f");
    
    function mouseMove() {
      d3.select("#focus")
        .attr("display", null);
      
      var xDisp = d3.mouse(this)[0];
      var xCoord = x.invert(xDisp);
      var i = bisect_x(mu, xCoord, 1);
      x0 = mu[i-1];
      x1 = mu[i];
      
      // Best-fit E(B-V)
      var y0 = best[i-1];
      var y1 = best[i];
      var xFactor = (xCoord-x0) / (x1-x0);
      var yCoord = y0 + (y1-y0)*xFactor;
      var yDisp = y(yCoord);
      
      // Statistics from samples of E(B-V)
      var ESamp = []
      for (var k = 0; k < samples.length; k++) {
        y0 = samples[k][i-1];
        y1 = samples[k][i];
        ESamp.push(y0 + (y1-y0)*xFactor);
      }
      ESamp.sort(d3.ascending);
      var ELow = d3.quantile(ESamp, 0.1587);
      var EHigh = d3.quantile(ESamp, 0.8413);
      var EMed = d3.median(ESamp);
      
      var yLow = y(ELow);
      var yHigh = y(EHigh);
      var yMed = y(EMed);
      var xDispLeft = x(xVals[0]);
      
      DM = Math.pow(10, xCoord/5 - 2);
      
      d3.select("#x-indicator")
        .attr("y1", y(0))
        .attr("y2", yMed)
        .attr("x1", xDisp)
        .attr("x2", xDisp);
      
      d3.select("#y-indicator")
        .attr("y1", yMed)
        .attr("y2", yMed)
        .attr("x1", xDispLeft)
        .attr("x2", xDisp);
      
      d3.select("#y-spread-indicator")
        .attr("x", xDispLeft)
        .attr("y", yHigh)
        .attr("width", d3.max([0,xDisp-xDispLeft]))
        .attr("height", yLow-yHigh);
      
      d3.select("#dist-label")
        .text("d = " + text_formatter(DM) + " kpc");
      
      d3.select("#EBV-label")
        .text("E(B-V) = " + text_formatter(EMed));
      
      d3.select("#EBV-plus")
        .text("+" + text_formatter(EHigh-EMed));
      
      d3.select("#EBV-minus")
        .text("-" + text_formatter(EMed-ELow));
    }
  };
  
  linePlotContainer = ".line-plot-container";
  
  // Initial data
  mu = d3.range(4, 19.01, 0.5);
  best = Array.apply(null, new Array(mu.length)).map(Number.prototype.valueOf,0);
  samples = [best];
  converged = 1;
  tableData = "";
  noData = 0;
  
  // Current view
  lCur = 0;
  bCur = 0;
  rCur = 0;
  
  // Draw initial plot
  //drawPlot(linePlotContainer, 0, mu, best, samples, converged, noData);
  
  // Execute the query
  submitTimeLast = 0;
  queryTimeout = 5000;
  queryLock = false;
  
  function submitQuery(lon, lat) {
    // Minimum time between queries
    var submitTime = $.now();
    if (queryLock && ((submitTime - submitTimeLast) < queryTimeout)) {
      console.log("Query already in progress.");
      return false;
    } else {
      submitTimeLast = submitTime;
      queryLock = false;
    }
    
    // Remove initial instructional alert
    $("#enter-coords-alert").alert("close");
    
    // Read and validate input
    var updateInputBoxes = false;
    
    if((typeof(lon) === 'undefined') || (typeof(lat) === 'undefined')) {
      lon = parseAngle($('input[name="gal-l"]').val());
      lat = parseAngle($('input[name="gal-b"]').val());
      
      console.log("lon:");
      console.log(lon);
      console.log("lat:");
      console.log(lat);
      
      //if ((!$.isNumeric(lon)) || (!$.isNumeric(lat))) {
      
      if ((lon.val === null) || (lat.val === null)) {
        showBadCoordsAlert();
        return;
      } else if ((lat.val < -90) || (lat.val > 90)) {
        showBadCoordsAlert();
        return;
      } else {
        hideBadCoordsAlert();
      }
      
      if (useGalactic & ((lon.format == "hms") || (lat.format == "hms"))) {
        showCustomAlert("hh:mm:ss format detected. Did you mean to use Equatorial coordinates?");
      } else {
        hideCustomAlert();
      }
      
      lon = lon.val;
      lat = lat.val;
      
    } else {
      updateInputBoxes = true;
      hideBadCoordsAlert();
      hideCustomAlert();
    }
    
    // Convert from (RA,Dec) to (l,b) if necessary
    var lIn = lon;
    var bIn = lat;
    
    if (!useGalactic) {
      var coordsGal = equ2gal_J2000(lIn, bIn);
      lIn = coordsGal.l;
      bIn = coordsGal.b;
      
      console.log("(l,b) = (" + coordsGal.l + ", " + coordsGal.b + ")");
    }
    
    data = {
      l: lIn,
      b: bIn
    };
    
    // Animate query button
    $("#submit-btn-icon").attr("class", "fa fa-spinner fa-spin fa-lg");
    
    // Handle AJAX request
    queryLock = true;
    
    $.ajax({
      type: "POST",
      url: "/gal-lb-query",
      contentType: "application/json; charset=utf-8",
      data: JSON.stringify(data),
      success: function(data) {
        queryLock = false;
        
        querySuccess = $.parseJSON(data.success);
        mu = $.parseJSON(data.mu);
        best = $.parseJSON(data.best);
        samples = $.parseJSON(data.samples);
        converged = $.parseJSON(data.converged);
        tableData = $.parseJSON(data.table_data);
        
        lCur = $.parseJSON(data.l);
        bCur = $.parseJSON(data.b);
        rCur = $.parseJSON(data.radius);
        
        noData = 1 - querySuccess;
        
        drawPlotSafe(true, linePlotContainer, 500, mu, best, samples, converged, noData);
        
        $("#postage-stamp-1").attr("src", data.image1);
        $("#postage-stamp-2").attr("src", data.image2);
        $("#postage-stamp-3").attr("src", data.image3);
        $("#ps-label-1").text(data.label1);
        $("#ps-label-2").text(data.label2);
        $("#ps-label-3").text(data.label3);
        $("#submit-btn-icon").attr("class", "glyphicon glyphicon-search");
        
        if (querySuccess == 1) {
          toggleTableBtn(false);
          $("#table-btn").attr("href", tableData);
        } else {
          toggleTableBtn(true);
        }
        
        drawPSOverlays();
        
        if (updateInputBoxes) {
          var formatter_3f = d3.format(".3f");
          $('input[name="gal-l"]').val(formatter_3f(lon));
          $('input[name="gal-b"]').val(formatter_3f(lat));
        }
      },
      error: function() {
        queryLock = false;
        
        $("#submit-btn-icon").attr("class", "glyphicon glyphicon-ok");
        
        toggleTableBtn(true);
      }
    });
    
    return true;
  };
  
  // Bind the query to button click and enter key
  $("#submit-btn").click(function() { submitQuery(); });
  $("#gal-l-input").keypress(function(e) {
    var key = e.which;
    if (key == 13) {
      submitQuery();
    }
  });
  $("#gal-b-input").keypress(function(e) {
    var key = e.which;
    if (key == 13) {
      submitQuery();
    }
  });
  
  // Toggle ASCII table link
  function toggleTableBtn(disable) {
    d3.select("#table-btn").classed("disabled", disable);
  }
  
  
  /*
   * Postage Stamp Overlays
   */
  
  //drawPSOverlays();
  
  function drawPSOverlays() {
    if (!d3.select("#postage-stamp-div").classed("collapse in")) { return; }
    
    var psContainers = d3.selectAll(".ps-container");
    
    // Create SVG overlays, if they do not yet exist
    var psSVG = d3.selectAll(".ps-overlay");
    
    if (psSVG[0].length < 1) {
      psSVG = psContainers.append("svg")
        .attr("class", "ps-overlay")
        .style("position", "absolute")
        .style("top", "0px")
        .style("left", "0px");
      
      var psBullseye = psSVG.append("g")
        .attr("class", "ps-bullseye")
        .style("opacity", 0.75);
      
      psBullseye.append("circle")
        .attr("class", "ps-bullseye-outer")
        .attr("fill", "none")
        .attr("stroke", "#FFD35C")
        .attr("stroke-width", "3px")
        .attr("x", 0)
        .attr("y", 0);
      
      psBullseye.append("circle")
        .attr("class", "ps-bullseye-inner")
        .attr("fill", "#FFD35C")
        .attr("x", 0)
        .attr("y", 0);
      
      focus = psSVG.append("g")
        .attr("class", "ps-focus")
        .style("opacity", 0);
      
      focus.append("rect")
        .attr("class", "ps-text-bg");
      
      var psTxtEl = focus.append("text")
        .attr("class", "ps-text-indicator")
        .style("text-anchor", "start");
      
      psTxtEl.append("tspan")
        .text("l = 0")
        .attr("class", "ps-l-label");
      
      psTxtEl.append("tspan")
        .attr("class", "ps-b-label")
        .text("b = 0");
      
      psOverlayRect = psSVG.append("rect")
        .attr("class", "overlay");
      
      psOverlayRect.each(function(d,i) {
        var assocFocus = d3.selectAll(".ps-focus")[0][i];
        d3.select(this)
          .on("mouseover", function() {
            d3.select(assocFocus).style("opacity", 1);
          })
          .on("mouseout", function() {
            d3.select(assocFocus).style("opacity", 0);
          });
      });
    }
    
    psContainers.each(function(d,i) {
      var imgProp = getPosExtent(d3.select(this).select(".ps-img")[0]);
      
      d3.select(this).select(".ps-overlay")
        .attr("width", imgProp.width + "px")
        .attr("height", imgProp.height + "px")
        .style("left", imgProp.left + "px")
        .style("top", imgProp.top + "px");
      
      // Update bullseye
      var rOuter = imgProp.width / 40;
      rOuter = d3.max([rOuter, 8]);
      rOuter = d3.min([rOuter, 24]);
      
      var rInner = rOuter / 4.
      
      d3.select(this).select(".ps-bullseye-outer")
        .attr("r", rOuter);
      d3.select(this).select(".ps-bullseye-inner")
        .attr("r", rInner);
      d3.select(this).select(".ps-bullseye")
        .attr("transform", "translate(" + imgProp.width/2. + "," + imgProp.height/2. + ")");
      
      // Update coordinate labels
      var psScaling = imgProp.width / 200;
      psScaling = d3.max([psScaling, 0.5]);
      psScaling = d3.min([psScaling, 3.]);
      
      var psFontSize = 11 * psScaling;
      
      var psTxt = d3.select(this).select(".ps-text-indicator")
        .attr("x", 1.2*psFontSize + "pt")
        .attr("y", 1.2*psFontSize + "pt")
        .style("font-size", psFontSize + "pt");
      
      lLabPS = psTxt.select(".ps-l-label");
      
      lTxtTmp = lLabPS.text();
      
      lLabPS.attr("x", 0.5*psFontSize + "pt")
        .text("l = 359.9\u00B0"); // Set l-label to longest possible value
      
      psTxt.select(".ps-b-label")
        .attr("x", 0.5*psFontSize + "pt")
        .attr("dy", psFontSize + "pt");
      
      var psTxtBounds = psTxt[0][0].getBBox();
      
      lLabPS.text(lTxtTmp); // Set l-label back to previous value
      
      xMargin = 0.5 * psTxtBounds.x;
      yMargin = 0.5 * psTxtBounds.y;
      
      d3.select(this).select(".ps-text-bg")
        .attr("x", (psTxtBounds.x - xMargin) + "px")
        .attr("y", (psTxtBounds.y - yMargin) + "px")
        .attr("width", (psTxtBounds.width + 2*xMargin) + "px")
        .attr("height", (psTxtBounds.height + 2*yMargin) + "px")
        .attr("rx", 0.75*xMargin + "px")
        .attr("ry", 0.75*xMargin + "px");
      
      // Update mouse overlay
      var self = this;
      
      // Properties of Postage-stamp Gnomonic projection
      var lng0 = deg2rad(lCur);
      var cLat0 = Math.cos(deg2rad(bCur));
      var sLat0 = Math.sin(deg2rad(bCur));
      var xMaxProj = GnomonicProj(deg2rad(rCur), 0, 0, 1, 0).x;
      
      var lb_formatter = d3.format(".1f");
      
      var get_ps_lb = function(objOverlay) {
        var xDisp = d3.mouse(objOverlay)[0];
        var yDisp = d3.mouse(objOverlay)[1];
        
        var xProj = -2 * (xDisp / imgProp.width - 0.5) * xMaxProj;
        var yProj = -2 * (yDisp / imgProp.height - 0.5) * xMaxProj;
        
        var coords = GnomonicProjInv(xProj, yProj, lng0, cLat0, sLat0);
        
        return {"l": rad2deg(coords.lng), "b": rad2deg(coords.lat)};
      }
      
      d3.select(this).select(".overlay")
        .attr("width", imgProp.width)
        .attr("height", imgProp.height)
        .on("mousemove", function() {
          /*
          var xDisp = d3.mouse(this)[0];
          var yDisp = d3.mouse(this)[1];
          
          var xProj = -2 * (xDisp / imgProp.width - 0.5) * xMaxProj;
          var yProj = -2 * (yDisp / imgProp.height - 0.5) * xMaxProj;
          
          var coords = GnomonicProjInv(xProj, yProj, lng0, cLat0, sLat0);
          */
          
          var coordsGal = get_ps_lb(this);
          
          var lTxt = "";
          var bTxt = "";
          
          if (useGalactic) {
            lTxt = "l = " + lb_formatter(coordsGal.l) + "\u00B0";
            bTxt = "b = " + lb_formatter(coordsGal.b) + "\u00B0";
          } else {
            var coordsEqu = gal2equ_J2000(coordsGal.l, coordsGal.b);
            lTxt = "\u03B1 = " + lb_formatter(coordsEqu.a) + "\u00B0";
            bTxt = "\u03B4 = " + lb_formatter(coordsEqu.d) + "\u00B0";
          }
          
          d3.select(self).select(".ps-l-label")
            .text(lTxt); // \u2113
          d3.select(self).select(".ps-b-label")
            .text(bTxt);
        })
        .on("click", function() {
          var coordsGal = get_ps_lb(this);
          
          if (useGalactic) {
            submitQuery(coordsGal.l, coordsGal.b);
            //}
          } else {
            var coordsEqu = gal2equ_J2000(coordsGal.l, coordsGal.b);
            submitQuery(coordsEqu.a, coordsEqu.d);
          }
        });
    });
  }
  
  function getPosExtent(obj) {
    var xy0 = $(obj).position();
    var x0 = xy0.left;
    var y0 = xy0.top;
    
    x0 += parseInt($(obj).css("padding-left"), 10);
    y0 += parseInt($(obj).css("padding-top"), 10);
    
    x0 += parseInt($(obj).css("margin-left"), 10);
    y0 += parseInt($(obj).css("margin-top"), 10);
    
    var w = parseInt($(obj).css("width"), 10);
    var h = parseInt($(obj).css("height"), 10);
    
    return {"left": x0, "top": y0, "width": w, "height": h};
  }
  
  // Gnomonic projection
  function GnomonicProj(lng, lat, lng0, cLat0, sLat0) {
    var cLat = Math.cos(lat);
    var sLat = Math.sin(lat);
    
    var cDLng = Math.cos(lng - lng0);
    var sDLng = Math.sin(lng - lng0);
    
    var aProj = 1. / (sLat0 * sLat + cLat0 * cLat * cDLng);
    
    var xProj = aProj * cLat * sDLng;
    var yProj = aProj * (cLat0 * sLat - sLat0 * cLat * cDLng);
    
    return {"x": xProj, "y": yProj};
  }
  
  function GnomonicProjInv(xProj, yProj, lng0, cLat0, sLat0) {
    var rho = Math.sqrt(xProj*xProj + yProj*yProj);
    var c = Math.atan(rho);
    
    var cc = Math.cos(c);
    var sc = Math.sin(c);
    
    var lat = Math.asin(cc * sLat0 + yProj * sc * cLat0 / rho);
    var lng = lng0 + Math.atan2((xProj * sc), (rho * cLat0 * cc - yProj * sLat0 * sc));
    
    if (lng > 2*Math.PI) {
      lng -= 2*Math.PI;
    } else if (lng < 0) {
      lng += 2*Math.PI;
    }
    
    return {"lng": lng, "lat": lat};
  }
  
  // Handle window resizing
  var debounce = function(fn, timeout) {
    var timeoutID = -1;
    return function() {
      if (timeoutID > -1) {
        window.clearTimeout(timeoutID);
      }
      timeoutID = window.setTimeout(fn, timeout);
    }
  };
  
  function listenResize(obj, fn, dt) {
    var w0 = $(obj).width();
    var h0 = $(obj).height();
    
    setInterval(function() {
      var w1 = $(obj).width();
      var h1 = $(obj).height();
      
      if((w1 != w0) || (h1 != h0)) {
        w0 = w1;
        h0 = h1;
        console.log("resized");
        fn();
      }
    }, dt);
  }
  
  var debouncedDrawPlot = debounce(function() {
    drawPlotSafe(false, linePlotContainer, 200, mu, best, samples, converged, noData);
  }, 125);
  
  var debouncedDrawPSOverlays = debounce(function() {
    drawPSOverlays();
  }, 250);
  
  $(window).resize(debouncedDrawPlot);
  
  listenResize(d3.select(".ps-container")[0][0], drawPSOverlays, 500);
  
});