/**
 * GrapesJS Booking Blocks Plugin
 *
 * Provides custom blocks for the booking system:
 * - Staff Card
 * - Booking Button
 * - Price Table
 * - Access Map
 * - Shift Display
 * - Testimonial
 */
(function() {
    'use strict';

    var plugin = function(editor) {
        var bm = editor.BlockManager;
        var category = '予約コンポーネント';

        // Staff Card
        bm.add('staff-card', {
            label: 'スタッフカード',
            category: category,
            content: '<div class="staff-card" style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;text-align:center;max-width:280px;">' +
                '<div style="width:80px;height:80px;border-radius:50%;background:#f3e8ff;margin:0 auto 12px;display:flex;align-items:center;justify-content:center;">' +
                    '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#9333ea" stroke-width="2"><path d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z"/></svg>' +
                '</div>' +
                '<h3 style="font-size:18px;font-weight:700;margin-bottom:4px;">スタッフ名</h3>' +
                '<p style="font-size:13px;color:#6b7280;margin-bottom:12px;">自己紹介テキスト</p>' +
                '<a href="#" style="display:inline-block;background:#8c876c;color:#fff;padding:8px 24px;border-radius:6px;text-decoration:none;font-size:14px;">予約する</a>' +
            '</div>',
        });

        // Booking Button
        bm.add('booking-button', {
            label: '予約ボタン',
            category: category,
            content: '<a href="#" style="display:inline-block;background:#8c876c;color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-size:16px;font-weight:600;text-align:center;">今すぐ予約する</a>',
        });

        // Price Table
        bm.add('price-table', {
            label: '料金表',
            category: category,
            content: '<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;overflow:hidden;max-width:400px;">' +
                '<div style="background:#8c876c;color:#fff;padding:16px;text-align:center;">' +
                    '<h3 style="font-size:18px;font-weight:700;">料金プラン</h3>' +
                '</div>' +
                '<table style="width:100%;border-collapse:collapse;">' +
                    '<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:12px 16px;">20分コース</td><td style="padding:12px 16px;text-align:right;font-weight:700;">¥3,000</td></tr>' +
                    '<tr style="border-bottom:1px solid #e5e7eb;"><td style="padding:12px 16px;">40分コース</td><td style="padding:12px 16px;text-align:right;font-weight:700;">¥5,000</td></tr>' +
                    '<tr><td style="padding:12px 16px;">60分コース</td><td style="padding:12px 16px;text-align:right;font-weight:700;">¥7,000</td></tr>' +
                '</table>' +
            '</div>',
        });

        // Access Map
        bm.add('access-map', {
            label: 'アクセスマップ',
            category: category,
            content: '<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:20px;">' +
                '<h3 style="font-size:18px;font-weight:700;margin-bottom:12px;">アクセス</h3>' +
                '<div style="background:#f3f4f6;border-radius:8px;height:250px;display:flex;align-items:center;justify-content:center;color:#6b7280;font-size:14px;">' +
                    'Google Maps 埋め込みエリア' +
                '</div>' +
                '<p style="margin-top:12px;font-size:14px;color:#333;">〒xxx-xxxx 住所をここに入力</p>' +
            '</div>',
        });

        // Shift Display
        bm.add('shift-display', {
            label: 'シフト表示',
            category: category,
            content: '<div style="background:#f1f0ec;border-radius:12px;padding:20px;">' +
                '<h3 style="font-size:18px;font-weight:700;color:#333;margin-bottom:12px;">本日の出勤</h3>' +
                '<div style="display:flex;gap:12px;flex-wrap:wrap;">' +
                    '<div style="background:#fff;border-radius:8px;padding:12px;text-align:center;min-width:100px;">' +
                        '<div style="font-weight:600;">スタッフA</div>' +
                        '<div style="font-size:12px;color:#6b7280;">10:00-18:00</div>' +
                    '</div>' +
                    '<div style="background:#fff;border-radius:8px;padding:12px;text-align:center;min-width:100px;">' +
                        '<div style="font-weight:600;">スタッフB</div>' +
                        '<div style="font-size:12px;color:#6b7280;">12:00-20:00</div>' +
                    '</div>' +
                '</div>' +
            '</div>',
        });

        // Testimonial
        bm.add('testimonial', {
            label: 'お客様の声',
            category: category,
            content: '<div style="background:#fff;border:1px solid #e5e7eb;border-radius:12px;padding:24px;max-width:500px;">' +
                '<div style="font-size:32px;color:#d4a574;line-height:1;">&#10077;</div>' +
                '<p style="font-size:15px;line-height:1.8;color:#333;margin:8px 0 16px;">とても素敵な時間を過ごせました。的確なアドバイスをいただけて、前向きな気持ちになれました。</p>' +
                '<div style="display:flex;align-items:center;gap:8px;">' +
                    '<div style="width:36px;height:36px;border-radius:50%;background:#f3e8ff;"></div>' +
                    '<div><div style="font-weight:600;font-size:13px;">お客様名</div><div style="font-size:12px;color:#6b7280;">2026年3月</div></div>' +
                '</div>' +
            '</div>',
        });

        // Hero Section
        bm.add('hero-section', {
            label: 'ヒーローセクション',
            category: category,
            content: '<div style="background:linear-gradient(135deg,#8c876c,#b8a88a);padding:60px 24px;text-align:center;color:#fff;border-radius:12px;">' +
                '<h1 style="font-size:36px;font-weight:700;margin-bottom:12px;">サロン名</h1>' +
                '<p style="font-size:18px;opacity:0.9;margin-bottom:24px;">あなたの未来を照らす特別なひとときを</p>' +
                '<a href="#" style="display:inline-block;background:#fff;color:#8c876c;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:700;">予約はこちら</a>' +
            '</div>',
        });
    };

    // Register as GrapesJS plugin
    if (typeof grapesjs !== 'undefined') {
        grapesjs.plugins.add('grapesjs-booking-blocks', plugin);
    } else {
        // Defer registration
        window.grapesjsBookingBlocks = plugin;
    }
})();
