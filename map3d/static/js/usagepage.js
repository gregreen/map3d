$(document).ready(function() {
  
  function selectText(container) {
    if (document.selection) {
      var range = document.body.createTextRange();
      range.moveToElementText(container);
      range.select();
    } else if (window.getSelection) {
      var range = document.createRange();
      range.selectNode(container);
      window.getSelection().removeAllRanges();
      window.getSelection().addRange(range);
    }
  }
  
  function addSelectButtons() {
    d3.selectAll(".add-click-select")
      .each(function() {
        if(d3.select(this).select(".highlight").length == 0) {
          return;
        }
        
        var container = this;
        var codeBlock = d3.select(this).select(".highlight")[0][0];
        
        // Add overlay
        var overlay = d3.select(container)
          .append("div")
            .attr("class", "top-right-overlay");
        
        overlay.on("click", function() {
          selectText(codeBlock);
          overlay.select(".overlay-msg")
            .transition().duration(500)
              .style("opacity", 1);
          overlay.select(".overlay-msg")
            .transition().delay(3000).duration(500)
              .style("opacity", 0);
        });
        
        // Add message to overlay
        overlay.append("span")
          .attr("class", "overlay-msg")
          .text("Ctrl/Cmd-C to copy")
          .style("opacity", 0);
        
        // Add copy icon to overlay
        var faSpan = overlay.append("span")
          .attr("class", "fa-stack fa-lg click-select");
        
        faSpan.append("i")
          .attr("class", "fa fa-square fa-stack-2x");
        
        faSpan.append("i")
          .attr("class", "fa fa-clipboard fa-stack-1x");
        
      });
  }
  
  addSelectButtons();
  
});
