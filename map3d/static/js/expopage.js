$(document).ready(function() {
  
  // Create a video element inside each div with the class ".video-placeholder"
  function fillVideoPlaceholders() {
    d3.selectAll(".video-placeholder")
      .each(function() {
        var container = d3.select(this);
        var srcBase = container.attr("data-src");
        var dataRes = container.attr("data-res");
        var propLoop = this.hasAttribute("data-loop");
        var resStr = pickResolution(dataRes);
        
        console.log("Selecting video of size " + resStr);
        
        // Create video element
        var videoEl = container.append("video")
          .attr("preload", "auto")
          .property("loop", propLoop)
          .property("controls", true)
          .attr("poster", srcBase + ".jpg")
          .attr("data-appear-top-offset", "250px");
        
        // Only load video sources when the user scrolls down to the video
        var loaded = false;
        $(this).appear();
        
        $(this).on("appear", function() {
          if (loaded) { return; }
          loaded = true;
          
          console.log("Loading " + srcBase);
          
          videoEl.append("source")
            .attr("src", srcBase + "_" + resStr + ".webm")
            .attr("type", 'video/webm; codecs="vp8"');
          videoEl.append("source")
            .attr("src", srcBase + "_" + resStr + ".ogv")
            .attr("type", 'video/ogg; codecs="theora"');
          videoEl.append("source")
            .attr("src", srcBase + "_" + resStr + ".mp4")
            .attr("type", 'video/mp4; codecs="avc1.42E01E"');
          videoEl.append("p")
            .text("Upgrade to a modern browser to see video.");
          
          //videojs(videoEl[0][0], {}, function() { console.log("Loaded " + srcBase); } );
        });
      });
  }
  
  // Pick a resolution appropriate to the screen size.
  // dataRes is a string containing a list of available video
  // resolutions, e.g., "1920x1080 1024x576". The substring
  // corresponding to the optimal resolution will be returned.
  function pickResolution(dataRes) {
    var availRes = dataRes.split(" ");
    
    var vidSpecs = [];
    
    for(var i=0; i<availRes.length; i++) {
      wh = availRes[i].split("x");
      
      vidSpecs.push({
        spec: availRes[i],
        width: wh[0],
        height: wh[1]
      });
    }
    
    var specComp = function(a, b) {
      return -(a.width*a.height - b.width*b.height);
    }
    
    vidSpecs.sort(specComp);
    
    for(var i=0; i<vidSpecs.length; i++) {
      if((screen.width > vidSpecs[i].width) || (screen.height > vidSpecs[i].width)) {
        return vidSpecs[i].spec;
      }
    }
    
    return vidSpecs[vidSpecs.length-1].spec;
  }
  
  fillVideoPlaceholders();
});
