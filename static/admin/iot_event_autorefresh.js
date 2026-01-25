// IoTEvent の changelist を一定間隔で自動リロードする

(function () {
  // 画面が IoTEvent の一覧のときだけ動けば OK
  // 一応パスで /admin/booking/iotevent/ を判定
  if (!window.location.pathname.includes("/admin/booking/iotevent/")) {
    return;
  }

  // 30秒ごとにリロード（好みで変えてOK）
  var INTERVAL_MS = 30000;

  setTimeout(function () {
    // フィルタ条件は維持したままリロード
    window.location.reload();
  }, INTERVAL_MS);
})();