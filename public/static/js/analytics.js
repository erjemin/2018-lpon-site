// analytics.js — Аналитика и счетчики посещений для oknardia.ru
// Версия: 1.0 | Дата: 2026-05-15
// Содержит: Google Analytics 4, Yandex.Metrika, Top.Mail.Ru

(function() {
  'use strict';

  // ============================================================================
  // Google Analytics 4 (GA4)
  // ID: GT-XXXXXXXX
  // ============================================================================
  (function() {
    var script = document.createElement('script');
    script.async = true;
    script.src = 'https://www.googletagmanager.com/gtag/js?id=GT-XXXXXXXX';
    document.head.appendChild(script);

    window.dataLayer = window.dataLayer || [];
    function gtag(){dataLayer.push(arguments);}
    window.gtag = gtag;
    gtag('js', new Date());
    gtag('config', 'GT-XXXXXXXX');
  })();

  // ============================================================================
  // Yandex.Metrika (Яндекс.Метрика)
  // ID: 12345678
  // ============================================================================
  (function() {
    window.ym = window.ym || function(){
      (window.ym.a = window.ym.a || []).push(arguments);
    };
    window.ym.l = 1 * new Date();

    // Загружаем скрипт Метрики
    var script = document.createElement('script');
    script.type = 'text/javascript';
    script.src = 'https://mc.yandex.ru/metrika/tag.js';
    document.head.appendChild(script);

    // Инициализируем Метрику
    window.ym(12345678, 'init', {
      trackHash: true,
      clickmap: true,
      referrer: document.referrer,
      url: location.href,
      accurateTrackBounce: true,
      trackLinks: true
    });
  })();

  // ============================================================================
  // Top.Mail.Ru counter (Рейтинг@Mail.ru)
  // ID: 1234567
  // ============================================================================
  (function() {
    var _tmr = window._tmr || (window._tmr = []);
    _tmr.push({
      id: "1234567",
      type: "pageView",
      start: (new Date()).getTime()
    });

    (function(d, w, id) {
      if (d.getElementById(id)) return;
      var ts = d.createElement("script");
      ts.type = "text/javascript";
      ts.async = true;
      ts.id = id;
      ts.src = "https://top-fwz1.mail.ru/js/code.js";

      var f = function() {
        var s = d.getElementsByTagName("script")[0];
        s.parentNode.insertBefore(ts, s);
      };

      if (w.opera == "[object Opera]") {
        d.addEventListener("DOMContentLoaded", f, false);
      } else {
        f();
      }
    })(document, window, "tmr-code");

    // Добавляем изображение для noscript
    if (!window.noScriptAdded) {
      window.noScriptAdded = true;
      var noscriptDiv = document.createElement('div');
      noscriptDiv.style.display = 'none';
      noscriptDiv.innerHTML = '<img src="https://top-fwz1.mail.ru/counter?id=1234567;js=na" style="position:absolute;left:-9999px;" alt="Top.Mail.Ru" />';
      document.body.appendChild(noscriptDiv);
    }
  })();

})();

// Экспортируем gtag в глобальный контекст для возможности использования в коде
// window.gtag доступна через глобальную переменную

