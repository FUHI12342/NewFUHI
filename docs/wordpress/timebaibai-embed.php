<?php
/**
 * Plugin Name: Timebaibai 埋め込み
 * Description: Timebaibaiの予約カレンダー・シフト表示をショートコードで埋め込み
 * Version: 1.0
 * Author: Timebaibai
 *
 * 使い方:
 *   [timebaibai type="booking" store="1" api_key="YOUR_KEY"]
 *   [timebaibai type="shift" store="1" api_key="YOUR_KEY"]
 *   [timebaibai type="booking" store="1" api_key="YOUR_KEY" height="700"]
 */

if (!defined('ABSPATH')) exit;

function timebaibai_embed_shortcode($atts) {
    $atts = shortcode_atts(array(
        'type'    => 'booking',
        'store'   => '1',
        'api_key' => '',
        'height'  => '',
        'base'    => 'https://timebaibai.com',
    ), $atts, 'timebaibai');

    if (empty($atts['api_key'])) {
        return '<p style="color:red;">Timebaibai: api_key が未設定です</p>';
    }

    $type = sanitize_text_field($atts['type']);
    if (!in_array($type, array('booking', 'shift'), true)) {
        return '<p style="color:red;">Timebaibai: type は booking または shift を指定してください</p>';
    }

    $store  = intval($atts['store']);
    $key    = sanitize_text_field($atts['api_key']);
    $base   = esc_url(rtrim($atts['base'], '/'));
    $height = $atts['height'] ? intval($atts['height']) : ($type === 'booking' ? 600 : 400);

    $url = sprintf('%s/embed/%s/%d/?api_key=%s', $base, $type, $store, $key);

    return sprintf(
        '<iframe src="%s" width="100%%" height="%d" style="border:none; max-width:100%%;" loading="lazy" title="Timebaibai %s"></iframe>',
        esc_url($url),
        $height,
        esc_attr($type === 'booking' ? '予約カレンダー' : 'シフト表示')
    );
}
add_shortcode('timebaibai', 'timebaibai_embed_shortcode');
