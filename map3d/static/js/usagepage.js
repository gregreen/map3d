$(document).ready(function() {
  
  function selectText(container) {
    if (document.selection) {
      var range = document.body.createTextRange();
      range.moveToElementText(container);
            range.select();
        } else if (window.getSelection) {
            var range = document.createRange();
            range.selectNode(container);
            window.getSelection().addRange(range);
    }
  }
  
  function addSelectButtons() {
    d3.select(".highlight")
      .each(function() {
        var container = this;
        d3.select(container)
          .append("div")
            .attr("class", "top-right-overlay click-select")
            .on('click', function() { selectText(container); } )
            .append("span")
              .attr("class", "fa-stack fa-lg");
        
        d3.select(container)
          .select(".click-select")
          .select("span")
            .append("i")
              .attr("class", "fa fa-square fa-stack-2x");
        
        d3.select(container)
          .select(".click-select")
          .select("span")
            .append("i")
              .attr("class", "fa fa-clipboard fa-stack-1x");
      });
  }
  
  addSelectButtons();
  
});
