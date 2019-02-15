function _do_group(select) {
    select = $(select);
	var c_grup = 0;
	var grupos = select.find("h2, div");
	var i;
	for (i=0; i<grupos.length; i++) {
		var g = grupos.eq(i);
		if (g.is("h2")) c_grup += 1;
        g.data("grupo", c_grup);
        g.addClass("g"+c_grup);
	}
    for (i=1; i<=c_grup; i++) {
        var divs = select.find("div.g"+i);
        if (divs.length==1) divs.addClass("unico");
    }
	return c_grup;
}

function en_grupo(item) {
    var g = item.data("grupo");
    var list = item.closest("table").find("h2, div");
    var i;
    var c = null;
    for (i=0; i<list.length; i++) {
        l = list.eq(i);
        if (l.is("h2")) {
            c = l.data("grupo");
            continue;
        }
        if (l.is(item)) {
            return c == g;
        }
    }
    return false;
}

function hermanos(h2) {
    var h2s = h2.closest("table").find("h2");
    var r = [null, null];
    var i;
    for (i=0;i<h2s.length; i++) {
        r[0] = h2s.eq(i)
    }
}

$(document).ready(function(){
    if ($("body").is(".simple")) return;
	if ($("table").length==0) return;
    $("div.cortar table").draggable().css("cursor", "move");

    jqMoveItems = "table.pesar"
    jqMoveProdu = "table.nopesar, table.albaran"

    _do_group(jqMoveItems);

    $(jqMoveProdu).each(function(){
        var tds = $(this).find("td");
        tds.sortable({
            items: "div.productor",
            connectWith: tds
        }).addClass("move");
    });

    $(jqMoveItems).each(function(){
        var tds = $(this).find("td");
        tds.sortable({
            items: "div:not(.unico)",
            connectWith: tds,
            stop: function(event, ui) {
                if (!en_grupo(ui.item)) {
                    $(this).sortable("cancel");
                }
            }
        }).addClass("move");
    });

    $(jqMoveItems).find("h2").each(function() {
        var h2 = $(this);
        h2.append("<span class='up'>&#x2b06;</span><span class='down'>&#x2b07;</span>");
    })
    $("span.up, span.down").click(function() {
        var t = $(this);
        var h2 = t.closest("h2");
        var up = t.attr("class") == "up";
        var g = h2.data("grupo");
        var grupo = $(".g"+g);

        var td =  h2.closest("td");
        var td_target = td[up?"prev":"next"]();
        if (td_target.is("td")) {
            if (td_target.find("div").length==0) {
                td_target.append(grupo);
                return;
            }

            if (up && td.find(" > *:first").is(h2)){
                td_target.append(grupo);
                return;
            }

            if (!up && td.find(" > *:last").is(grupo.last())) {
                td_target.prepend(grupo);
                return;
            }
        }

        var h2s = h2.closest("table").find("h2");
        var index = h2s.index(h2);
        if (up) {
            h2s.eq(index-1).before(grupo);
        } else {
            var g = h2s.eq(index+1).data("grupo");
            $(".g"+g).last().after(grupo);
        }
    })

	$("hr").click(function(){
		$(this).toggleClass("ocultar");
	});
})
