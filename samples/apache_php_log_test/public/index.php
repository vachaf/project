<?php
http_response_code(200);
header('Content-Type: text/html; charset=UTF-8');
?>
<!doctype html>
<html lang="ko">
<head>
  <meta charset="utf-8">
  <title>Apache PHP Log Test</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <main>
    <h1>Apache PHP Log Test</h1>
    <p>Apache access/security/error log 수집 검증용 최소 PHP 샘플입니다.</p>

    <nav>
      <ul>
        <li><a href="/search.php?q=test&page=1">Search with query string</a></li>
        <li><a href="/login.php">POST login form</a></li>
        <li><a href="/upload.php">Upload-like form</a></li>
        <li><a href="/forbidden.php">403 response</a></li>
        <li><a href="/error.php">500 response</a></li>
        <li><a href="/health.php">Health check</a></li>
        <li><a href="/not-found-test">404 response</a></li>
      </ul>
    </nav>
  </main>
  <script src="/static/app.js"></script>
</body>
</html>
