<?php
include "vendor/autoload.php";

use DiDom\Document;



$page = !empty($argv[1]) ? intval($argv[1]) : false;
$output = !empty($argv[2]) ? $argv[2] : false;

if ( !$page) {
    die("Please enter page");
}

$domain = "http://somevideosite.com";

$document = new Document($domain . "/all/$page/", true);

$videos = $document->find('.preview');

$list= [];
foreach($videos as $video) {
    $views = 0;

    $href = $video->find('a')[0]->getAttribute('href');

    if (strpos($href, "video")) {
        $text = $video->find(".name")[0]->text();

        $total_views_element = $video->find(".views-total");
        if ($total_views_element) {
            $views = $video->find(".views-total")[0]->text();
        }

        #echo "Getting ... " . $domain . $href . PHP_EOL;
        $document_video = new Document($domain . $href, true);
        $src = $document_video->find("video source")[0]->getAttribute('src');
        $result = ['link'=> $domain . $href, 'title'=>$text, 'views'=>$views, 'video' =>$src];
        $list[] = $result;
    }
}

$json = json_encode($list);

if ($output)
    file_put_contents($output, $json);
else
    echo $json;