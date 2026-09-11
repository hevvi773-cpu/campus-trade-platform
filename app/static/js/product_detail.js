/* 商品详情弹窗公共逻辑：admin / profile 共用（首页弹窗为独立实现） */

function pdEsc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}

function pdRow(label, value) {
    return '<div class="row mb-2"><div class="col-4 fw-bold">' + label + '</div><div class="col-8">' + value + '</div></div>';
}

function renderProductDetailHtml(d) {
    var html = pdRow('名称', pdEsc(d.name));
    html += pdRow('价格', '¥' + d.price);
    html += pdRow('类型', pdEsc(d.type_text));
    html += pdRow('卖家', pdEsc(d.seller));
    html += pdRow('联系方式', pdEsc(d.contact));
    html += pdRow('审核状态', pdEsc(d.status_text));
    html += pdRow('交易状态', pdEsc(d.sold_status_text));
    html += pdRow('发布时间', pdEsc(d.created_at));
    if (d.sold_time) html += pdRow('售出时间', pdEsc(d.sold_time));
    html += pdRow('描述', pdEsc(d.description) || '无');
    if (d.desc_image) html += '<div class="mb-2"><img src="/' + pdEsc(d.desc_image) + '" style="max-width:200px;border-radius:8px;"></div>';
    if (d.contact_image) html += '<div class="mb-2"><img src="/' + pdEsc(d.contact_image) + '" style="max-width:200px;border-radius:8px;"></div>';
    if (d.evaluation) {
        html += '<hr><div class="mt-3"><h6>⭐ 用户评价</h6>' +
            '<p>评分：' + '⭐'.repeat(d.evaluation.rating) + ' (' + d.evaluation.rating + '星)</p>' +
            '<p>评价人：' + pdEsc(d.evaluation.from_user) + '</p>' +
            '<p>内容：' + pdEsc(d.evaluation.content) + '</p>' +
            '<p>时间：' + pdEsc(d.evaluation.created_at) + '</p></div>';
    }
    return html;
}

function showProductDetail(pid, contentId, modalId) {
    var content = document.getElementById(contentId);
    content.innerHTML = '<div class="text-center py-4"><div class="spinner-border"></div></div>';
    fetch('/api/product/' + pid).then(function (r) { return r.json(); }).then(function (res) {
        if (res.code !== 0) { alert('加载失败'); return; }
        content.innerHTML = renderProductDetailHtml(res.data);
        new bootstrap.Modal(document.getElementById(modalId)).show();
    }).catch(function () { alert('加载失败'); });
}
