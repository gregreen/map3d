$(document).ready(function() {
  
  function fillVideoPlaceholders() {
    d3.selectAll(".video-placeholder")
      .each(function() {
        var container = d3.select(this);
        var srcBase = container.attr("data-src");
        var resStr = getResolution();
        
        console.log(srcBase);
        console.log(resStr);
        
        var videoEl = container.append("video")
          .attr("preload", "auto")
          .property("loop", true)
          .property("controls", true)
          .attr("poster", srcBase + ".jpg");
        
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
      });
  }
  
  function getResolution() {
    if ((screen.width < 1024) && (screen.height < 1024)) {
      return "960x720";
    } else if ((screen.width < 1920) && (screen.height < 1920)) {
      return "1024x768";
    } else {
      return "1920x1440";
    }
  }
  
  fillVideoPlaceholders();
});
