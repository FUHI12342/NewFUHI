<?php
/**
 * NewFUHI 埋め込みショートコード
 *
 * functions.php に貼り付けるか、カスタムプラグインとして使用。
 *
 * 使い方:
 *   [newfuhi_booking store_id="1" api_key="your_api_key_here"]
 *   [newfuhi_shift store_id="1" api_key="your_api_key_here"]
 *
 * オプション:
 *   height — iframe の高さ (デフォルト: 600px)
 *   width  — iframe の幅 (デフォルト: 100%)
 */

// 予約カレンダー埋め込み
function newfuhi_booking_shortcode($atts) {
    $atts = shortcode_atts(array(
        'store_id' => '1',
        'api_key'  => '',
        'height'   => '600',
        'width'    => '100%',
    ), $atts, 'newfuhi_booking');

    $store_id = intval($atts['store_id']);
    $api_key  = sanitize_text_field($atts['api_key']);
    $height   = sanitize_text_field($atts['height']);
    $width    = sanitize_text_field($atts['width']);

    $src = esc_url("https://timebaibai.com/embed/booking/{$store_id}/?api_key={$api_key}");

    return sprintf(
        '<iframe src="%s" width="%s" height="%s" style="border:none; max-width:100%%;" loading="lazy" title="予約カレンダー"></iframe>',
        $src, $width, $height
    );
}
add_shortcode('newfuhi_booking', 'newfuhi_booking_shortcode');

// シフト表示埋め込み
function newfuhi_shift_shortcode($atts) {
    $atts = shortcode_atts(array(
        'store_id' => '1',
        'api_key'  => '',
        'height'   => '400',
        'width'    => '100%',
    ), $atts, 'newfuhi_shift');

    $store_id = intval($atts['store_id']);
    $api_key  = sanitize_text_field($atts['api_key']);
    $height   = sanitize_text_field($atts['height']);
    $width    = sanitize_text_field($atts['width']);

    $src = esc_url("https://timebaibai.com/embed/shift/{$store_id}/?api_key={$api_key}");

    return sprintf(
        '<iframe src="%s" width="%s" height="%s" style="border:none; max-width:100%%;" loading="lazy" title="本日のシフト"></iframe>',
        $src, $width, $height
    );
}
add_shortcode('newfuhi_shift', 'newfuhi_shift_shortcode');
