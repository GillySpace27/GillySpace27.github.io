var albumBucketName = 'the-sun-now';

AWS.config.region = 'us-east-2';
AWS.config.credentials = new AWS.CognitoIdentityCredentials({
  IdentityPoolId: 'us-east-2:c9106db6-2689-430e-a584-ef4f17edef34',
});

var s3 = new AWS.S3({
  apiVersion: '2006-03-01',
  params: { Bucket: albumBucketName }
});

function getHtml(template) {
  return template.join('\n');
}

function listAlbums() {
  s3.listObjects({ Delimiter: '/' }, function (err, data) {
    if (err) {
      return alert('There was an error listing your albums: ' + err.message);
    } else {
      var albums = data.CommonPrefixes.map(function (commonPrefix) {
        var prefix = commonPrefix.Prefix;
        var albumName = decodeURIComponent(prefix.replace('/', ''));
        return getHtml([
          '<li>',
          '<button style="margin:5px;" onclick="viewAlbum(\'' + albumName + '\')">',
          albumName,
          '</button>',
          '</li>'
        ]);
      });
      var message = albums.length ?
        getHtml(['<p>Click on an album name to view it.</p>']) :
        '<p>You do not have any albums. Please Create album.';
      var htmlTemplate = [
        '<h2>Albums</h2>',
        message,
        '<ul>',
        getHtml(albums),
        '</ul>',
      ];
      document.getElementById('viewer').innerHTML = getHtml(htmlTemplate);
    }
  });
}

function viewAlbum(albumName) {
  var albumPhotosKey = encodeURIComponent(albumName) + '/';
  s3.listObjects({ Prefix: albumPhotosKey }, function (err, data) {
    if (err) {
      return alert('There was an error viewing your album: ' + err.message);
    }

    var href = this.request.httpRequest.endpoint.href;
    var bucketUrl = href + albumBucketName + '/';

    var photos = data.Contents.map(function (photo) {
      var photoKey = photo.Key;
      var photoUrl = bucketUrl + photoKey;
      var thumbUrl = bucketUrl + "renders/thumbs/" + photoKey.replace(albumPhotosKey, '');
      var photoName = photoKey.replace(albumPhotosKey, '').replace('_DrGilly_', ' ').replace("_hq.png", '');

      if (photoKey.includes("thumbs") || photoKey.includes("archive") || photoKey.includes("4500")) {
        return getHtml([]);
      } else if (photoKey.endsWith("png") && !photoKey.includes("_frame_for_thumb.png")) {
        return getHtml([
          '<a href="' + photoUrl + '" target="_blank"><img style="width:49%;" src="' + thumbUrl + '"/></a>',
        ]);
      } else {
        return getHtml([]);
      }
    });

    const videoThumbs = data.Contents.filter(item => item.Key.endsWith("_frame_for_thumb.png"));
    const videoFiles = data.Contents.filter(item => item.Key.endsWith(".mp4"));

    const videoHtmlSnippets = [];

    videoThumbs.forEach(thumbnail => {
      const baseName = thumbnail.Key.split("/").pop().replace("_frame_for_thumb.png", "");
      const videoMatch = videoFiles.find(v => v.Key.includes(baseName + ".mp4"));

      const thumbUrl = bucketUrl + thumbnail.Key;
      const videoUrl = videoMatch ? bucketUrl + videoMatch.Key : null;

      if (videoUrl) {
        videoHtmlSnippets.push(getHtml([
          '<div style="position: relative; display: inline-block; width: 49%; margin: 5px;">',
            '<a href="' + videoUrl + '" target="_blank">',
              '<img src="' + thumbUrl + '" style="width: 100%; border: 1px solid black;" />',
              '<div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);' +
              'font-size: 64px; color: white; text-shadow: 0 0 10px black;">▶</div>',
            '</a>',
          '</div>'
        ]));
      }
    });

    // Prepend the video previews to the image gallery
    photos = videoHtmlSnippets.concat(photos);

    var message = photos.length ?
      '<p>The following photos are present.</p>' :
      '<p>There are no photos in this album.</p>';
    var htmlTemplate = [
      '<div>',
      getHtml(photos),
      '</div>',
    ];
    document.getElementById('viewer').innerHTML = getHtml(htmlTemplate);
    const firstImg = document.getElementsByTagName('img')[0];
    if (firstImg) {
      firstImg.setAttribute('style', 'display:none;');
    }
  });
}