/**
 * Self-contained bookmarklet source for the Amazon order-history scraper.
 *
 * A bookmarklet runs in the amazon.co.uk / amazon.com origin and CANNOT import
 * app modules at runtime, so the parse logic below is a hand-inlined, trimmed
 * copy of the canonical parser in `webui/src/lib/amazon/scraper.ts`.
 *
 * KEEP IN SYNC with `scraper.ts`: selectors, money-as-strings handling, the
 * fail-loud invariants, and `SCRAPER_VERSION` must match. The canonical parser
 * is the one covered by the Playwright fixture tests; this derivative is what
 * the user actually runs.
 *
 * S7 (self-contained): NO remote fetch, NO `eval`, fully inlined. It is served
 * only from the user's own quid webui and runs against a live Amazon session,
 * so it is treated as a session-exfil surface and kept inspectable.
 *
 * Delivery (N1): the bookmarklet DOWNLOADS a `.json` file (primary — the user
 * uploads it into quid's "Import from browser" panel) and ALSO copies the JSON
 * to the clipboard as a convenience fallback.
 */

import { SCRAPER_VERSION } from './scraper.js';

/**
 * Re-exported for tests/version display. Sourced from the canonical parser so
 * the bookmarklet's reported version can never drift from `scraper.ts`.
 */
export const BOOKMARKLET_SCRAPER_VERSION = SCRAPER_VERSION;

/**
 * The bookmarklet body as a readable IIFE string. Rendered into a
 * `javascript:` URL by `buildBookmarkletHref()`. Inspectable on purpose.
 */
export const BOOKMARKLET_SOURCE = `(function(){
  var VERSION='${SCRAPER_VERSION}';
  var MONTHS={january:'01',february:'02',march:'03',april:'04',may:'05',june:'06',july:'07',august:'08',september:'09',october:'10',november:'11',december:'12'};
  function fail(d){throw new Error('Amazon page layout not recognised (scraper v'+VERSION+') — '+d+' The format may have changed.');}
  function txt(el){return (el&&el.textContent?el.textContent:'').replace(/\\s+/g,' ').trim();}
  function pick(root,sels){for(var i=0;i<sels.length;i++){var f=root.querySelector(sels[i]);if(f)return f;}return null;}
  function money(raw){if(!raw)return null;var m=raw.replace(/\\s+/g,' ').match(/[0-9][0-9.,]*[0-9]|[0-9]/);if(!m)return null;var v=m[0];if(v.indexOf('.')>=0){v=v.replace(/,/g,'');}else if(v.indexOf(',')>=0){var p=v.split(',');if(p.length===2&&p[1].length===2){v=p[0]+'.'+p[1];}else{v=v.replace(/,/g,'');}}if(!/^[0-9]+(\\.[0-9]+)?$/.test(v))return null;return v;}
  function ndate(raw){if(!raw)return null;var t=raw.replace(/\\s+/g,' ').trim();var iso=t.match(/\\b(\\d{4})-(\\d{2})-(\\d{2})\\b/);if(iso)return iso[1]+'-'+iso[2]+'-'+iso[3];var dmy=t.match(/\\b(\\d{1,2})\\s+([A-Za-z]+)\\s+(\\d{4})\\b/);if(dmy){var mo=MONTHS[dmy[2].toLowerCase()];if(mo)return dmy[3]+'-'+mo+'-'+('0'+dmy[1]).slice(-2);}var mdy=t.match(/\\b([A-Za-z]+)\\s+(\\d{1,2}),?\\s+(\\d{4})\\b/);if(mdy){var mo2=MONTHS[mdy[1].toLowerCase()];if(mo2)return mdy[3]+'-'+mo2+'-'+('0'+mdy[2]).slice(-2);}return null;}
  function inferDomain(h){var m=h.match(/amazon\\.[a-z.]+$/i);return m?m[0].toLowerCase():h.toLowerCase();}
  var CARD=['.order-card','.a-box-group.order','.js-order-card','.order'];
  var PAGE=['#ordersContainer','.your-orders-content-container','[data-testid=orders-container]','.a-section.your-orders-content'];
  var EMPTY=['.no-orders','#emptyOrdersList','[data-testid=no-orders]'];
  var IDSEL=['bdi[dir=ltr]','.yohtmlc-order-id bdi','[data-testid=order-id]'];
  var TOTSEL=['[data-testid=order-total] .a-text-bold','.yohtmlc-order-total .a-text-bold','.order-total .value','[data-testid=order-total]'];
  var DATESEL=['[data-testid=order-date]','.yohtmlc-order-date .a-color-secondary','.order-date .value','.a-color-secondary.value'];
  var TITLESEL=['.yohtmlc-product-title','.a-link-normal.yohtmlc-product-title','[data-testid=item-title]','.a-row .a-link-normal'];
  function valByLabel(card,re){var labels=card.querySelectorAll('.a-text-caps');for(var i=0;i<labels.length;i++){var label=labels[i];if(!re.test(txt(label)))continue;var col=label.closest('.a-column, .a-fixed-right-grid-col, li')||label.parentElement;if(!col)continue;var lt=txt(label);var rows=col.querySelectorAll('.a-row');for(var r=0;r<rows.length;r++){var t=txt(rows[r]);if(t&&t!==lt&&!re.test(t))return t;}var s=txt(col).replace(lt,'').replace(/^\\s+/,'').replace(/\\s+$/,'');if(s)return s;}return null;}
  function orderId(card){var idc=card.querySelector('.yohtmlc-order-id');if(idc){var fc=txt(idc).match(/\\d{3}-\\d{7}-\\d{7}/);if(fc)return fc[0];}var byLabel=valByLabel(card,/order\\s*#/i);var fl=byLabel?byLabel.match(/\\d{3}-\\d{7}-\\d{7}/):null;if(fl)return fl[0];for(var i=0;i<IDSEL.length;i++){var v=txt(card.querySelector(IDSEL[i]));var mm=v.match(/\\d{3}-\\d{7}-\\d{7}/);if(mm)return mm[0];}var ft=txt(card).match(/\\d{3}-\\d{7}-\\d{7}/);return ft?ft[0]:null;}
  function items(card){var out=[],seen=Object.create(null);for(var i=0;i<TITLESEL.length;i++){var nodes=card.querySelectorAll(TITLESEL[i]);for(var j=0;j<nodes.length;j++){var title=txt(nodes[j]);if(!title||seen[title])continue;seen[title]=1;var box=nodes[j].closest('.a-fixed-left-grid, .item-box, [data-testid=item-row]');var pe=box?box.querySelector('.a-price .a-offscreen, .item-price, [data-testid=item-price]'):null;out.push({title:title,quantity:1,price:money(txt(pe))});}if(out.length)break;}return out;}
  function status(card){var el=pick(card,['[data-testid=order-status]','.delivery-box__primary-text','.delivery-box .a-text-bold','.shipment-top-row .a-text-bold']);var v=txt(el);if(!v)return null;var rj=v.match(/\\b(cancelled|canceled|returned|refunded)\\b/i);if(rj)return rj[1];var ac=v.match(/\\b(delivered|shipped|closed|complete|completed)\\b/i);if(ac)return ac[1];return null;}
  function last4(card){var m=txt(card).match(/(?:ending in|ending|••••|\\*{4})\\s*(\\d{4})/i);return m?m[1]:null;}
  function orderUrl(card,domain){var a=card.querySelector('a[href*=order-details], a[href*=orderID], a[href*="css/order-details"]');if(!a)return null;var href=a.getAttribute('href')||'';if(!href)return null;if(/^https?:\\/\\//.test(href))return href;return 'https://www.'+domain+(href.charAt(0)==='/'?'':'/')+href;}
  function card2order(card,domain,index){var id=orderId(card);if(!id)fail('order card #'+(index+1)+' has no recognisable order id.');var total=money(valByLabel(card,/^\\s*total\\s*$/i))||money(txt(pick(card,TOTSEL)));if(!total)fail('order '+id+' has no parseable total.');var date=ndate(valByLabel(card,/order\\s*placed/i))||ndate(txt(pick(card,DATESEL)))||'';return {orderId:id,orderDate:date,total:total,currency:null,status:status(card),items:items(card),shipments:[],paymentLast4:last4(card),orderUrl:orderUrl(card,domain)};}
  function parse(doc,domain){var cards=[];for(var i=0;i<CARD.length;i++){var f=doc.querySelectorAll(CARD[i]);if(f.length){cards=Array.prototype.slice.call(f);break;}}if(!cards.length){var isPage=PAGE.some(function(m){return doc.querySelector(m);});var isEmpty=EMPTY.some(function(m){return doc.querySelector(m);});if(isPage&&!isEmpty)fail('no order cards were found on the orders page.');return {scraperVersion:VERSION,domain:domain,orders:[]};}var orders=[];for(var k=0;k<cards.length;k++){try{orders.push(card2order(cards[k],domain,k));}catch(e){throw new Error(e.message+' (parsed '+orders.length+' of '+cards.length+' orders before failing — re-run after Amazon\\'s layout is supported again).');}}return {scraperVersion:VERSION,domain:domain,orders:orders};}
  try{
    var domain=inferDomain(location.host);
    var payload=parse(document,domain);
    if(!payload.orders.length){alert('quid: no Amazon orders found on this page. Open your Orders page (Returns & Orders) and try again.');return;}
    var json=JSON.stringify(payload,null,2);
    var blob=new Blob([json],{type:'application/json'});
    var url=URL.createObjectURL(blob);
    var a=document.createElement('a');
    a.href=url;a.download='amazon-orders-'+domain+'-'+new Date().toISOString().slice(0,10)+'.json';
    document.body.appendChild(a);a.click();document.body.removeChild(a);
    setTimeout(function(){URL.revokeObjectURL(url);},2000);
    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(json).catch(function(){});}
    alert('quid: scraped '+payload.orders.length+' Amazon orders. The .json file was downloaded (and copied to your clipboard). Upload it in quid → Amazon → Import from browser.');
  }catch(err){
    alert('quid: '+(err&&err.message?err.message:'scrape failed')+'\\n\\nNothing was exported. The CSV import is the reliable fallback.');
  }
})();`;

/**
 * Build the draggable `javascript:` bookmarklet URL. The source is
 * URL-encoded so it survives being dropped onto the bookmarks bar.
 */
export function buildBookmarkletHref(): string {
	return 'javascript:' + encodeURIComponent(BOOKMARKLET_SOURCE);
}
