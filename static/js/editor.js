(function() {

    function clearResults() {
        $('#result').empty();
    }

    function appendResult(str) {
        $('#result').append("<li>" + str + "</li>");
    }

    function save(draft) {
        var formData = $('#edit_form').serializeArray();
        formData.push({'name': 'draft', 'value': draft});
        $.ajax({
            type: "POST",
            url: "/api/save",
            data: formData,
            success: function saveSuccess(data) {
                appendResult("Saved post " + data.id);
                $('#post_id').val(data.id);
                addPermalink(draft, data.id, data.permalink);
                fetchContexts(draft, data.id, data.permalink);
            },
            error: function saveError(data) {
                appendResult("Failed to save post " + data.error);
            }
        });
    }

    function fetchContexts(draft, id, permalink) {
        callback = syndicateToTwitter;
        var formData = $('#edit_form').serializeArray();
        appendResult("Fetching Contexts");
        $.ajax({
            type: "POST",
            data: formData,
            url: "/api/fetch_contexts",
            success: function fetchSuccess(data) {
                if (data.success) {
                    appendResult("Success");
                } else {
                    appendResult("Failure " + data.error);
                }
                callback(draft, id, permalink);
            },
            error: function fetchFailure(data) {
                appendResult("Failure " + data.error);
                callback(draft, id, permalink);
            }
        });
    }

    function syndicateToTwitter(draft, id, permalink) {
        var callback = syndicateToFacebook

        if (!draft && $("#send_to_twitter").prop("checked")) {
            appendResult("Syndicating to Twitter");

            var previewField = $("#tweet_preview");
            var preview = null;
            if (previewField) {
                preview = previewField.val();
            }

            $.ajax({
                type: "POST",
                url: "/api/syndicate_to_twitter",
                data: {
                    "post_id": id,
                    "tweet_preview": preview
                },
                success: function tweetSuccess(data) {
                    if (data.success) {
                        appendResult("Success: <a href=\"" + data.twitter_permalink + "\">Twitter</a>");
                    } else {
                        appendResult("Failure " + data.error);
                    }
                    callback(draft, id, permalink);
                },
                error:  function tweetFailure(data) {
                    appendResult("Failure " + data.error);
                    callback(draft, id, permalink);
                }
            });

        } else {
            callback(draft, id, permalink);
        }
    }

    function syndicateToFacebook(draft, id, permalink) {
        var callback = sendWebmentions;

        if (!draft && $("#send_to_facebook").prop("checked")) {
            appendResult("Syndicating to Facebook");
            $.ajax({
                type: "POST",
                url: "/api/syndicate_to_facebook",
                data: {"post_id": id },
                success: function fbSuccess(data) {
                    if (data.success) {
                        appendResult("Success: <a href=\"" + data.facebook_permalink + "\">Facebook</a>");
                    } else {
                        appendResult("Failure " + data.error);
                    }
                    callback(draft, id, permalink);
                },
                error: function fbError(data) {
                    appendResult("Failure " + data.error);
                    callback(draft, id, permalink);
                }

            });
        } else {
            callback(draft, id, permalink);
        }

    }

    function sendWebmentions(draft, id, permalink) {
        var callback = sendPushNotification;

        if (!draft && $("#send_webmentions").prop("checked")) {
            appendResult("Sending Webmentions");
            $.ajax({
                type: "POST",
                url: "/api/send_webmentions",
                data: {"post_id": id },
                success: function wmSuccess(data) {
                    if (data.success) {
                        appendResult("Success");
                        for (var ii = 0 ; ii < data.results.length ; ++ii) {
                            var result = data.results[ii];
                            if (result.success) {
                                appendResult("Sent to <a href=\"" + result.target + "\">" + result.target + "</a>");
                            } else {
                                appendResult("Failure for <a href=\"" + result.target + "\">" + result.target + "</a>: " + result.explanation);
                            }
                        }
                    } else {
                        appendResult("Failure: " + data.error);
                    }
                    callback(draft, id, permalink);
                },
                error: function wmFailure(data) {
                    appendResult("Failure: " + data.error);
                    callback(draft, id, permalink);
                }
            });
        } else {
            callback(draft, id, permalink);
        }

    }

    function sendPushNotification(draft, id, permalink) {
        callback = finishPosting;

        if (!draft) {
            appendResult("Sending PuSH notification");
            $.ajax({
                type: "POST",
                url: "/api/send_push_notification",
                data: {"post_id": id},
                success: function pushComplete(data) {
                    if (data.success) {
                        appendResult("Success");
                    } else {
                        appendResult("Failure: " + data.error);
                    }
                    callback(draft, id, permalink);
                },
                error: function pushError(data) {
                    appendResult("Failure: " + data.error);
                    callback(draft, id, permalink);
                }
            });
        }
        else {
            callback(draft, id, permalink);
        }
    }

    function addPermalink(draft, id, permalink) {
        appendResult("<a href=\"" + permalink + "\" target=\"_ new\">View Post</a>");
    }

    function finishPosting(draft, id, permalink) {
        appendResult("Done at " + new Date($.now()).toTimeString());
        //$('#preview').css('display', 'block');
        //$('#preview').attr('src', '/admin/preview?id=' + id);
    }

    function uploadCompleteHandler(data) {

        appendResult("finished uploading to " + data.path);

        var content_text_area = $("#content");
        var content_format = $("#content_format").val();

        if (content_format == 'markdown') {
            content_text_area.val( content_text_area.val() + '\n![](' + data.path + ')');
        }
        else {
            content_text_area.val( content_text_area.val() + '\n<img src="' + data.path + '"/>');
        }
    }

    function uploadErrorHandler(data, status, errorThrown) {
        appendResult("upload failed with " + status + ", " + errorThrown);
    }

    function appendResult(str) {
        $('#result').append("<li>" + str + "</li>");
    }


    var short_url_length = 22;
    var short_url_length_https = 23;
    var media_url_length = 23;

    /* splits a text string into text and urls */
    function classifyText(text) {
        var result = [];

        var match;
        var lastIndex = 0;
        var urlRegex = /https?:\/\/[_a-zA-Z0-9.\/\-!#$%?]+/g;
        while ((match = urlRegex.exec(text)) != null) {
            var subtext = text.substring(lastIndex, match.index);
            if (subtext.length > 0) {
                result.push({type: 'text', value: subtext});
            }
            result.push({type: 'url', value: match[0]});
            lastIndex = urlRegex.lastIndex;
        }

        var subtext = text.substring(lastIndex);
        if (subtext.length > 0) {
            result.push({type: 'text', value: subtext});
        }

        return result;
    }

    function estimateLength(classified) {
        return classified.map(function(item){
            if (item.type == 'url') {
                var urlLength = item.value.startsWith('https') ? short_url_length_https : short_url_length;
                if (item.hasOwnProperty('prefix')) {
                    urlLength += item.prefix.length;
                }
                if (item.hasOwnProperty('suffix')) {
                    urlLength += item.suffix.length;
                }
                return urlLength;
            }
            return item.value.length;
        }).reduce(function(a, b){ return a + b; }, 0);
    }

    function shorten(classified, target) {
        for (;;) {
            var length = estimateLength(classified);
            if (length <= target) {
                return classified;
            }

            var diff = length - target;
            var shortened = false;

            for (var ii = classified.length-1; !shortened && ii >= 0 ; ii--) {
                var item = classified[ii];
                if (item['required']) {

                }
                else if (item.type == 'url') {
                    classified.splice(ii, 1);
                    shortened = true;
                }
                else if (item.type == 'text') {
                    if (item.value.length > diff + 3) {
                        var truncated = item.value.substring(0, item.value.length-diff-4);
                        // remove .'s and spaces from the end of the truncated string
                        while ([' ', '.'].indexOf(truncated[truncated.length-1]) >= 0) {
                            truncated = truncated.substring(0, truncated.length-1);
                        }
                        classified[ii] = {type: 'text', value:  truncated + '...'};
                        shortened = true;
                    }
                    else {
                        classified.splice(ii, 1);
                        shortened = true;
                    }
                }
            }
        }
    }

    function classifiedToString(classified) {
        return classified.map(function(item) {
            var result = '';
            if (item != null) {

                if (item.hasOwnProperty('prefix')) {
                    result += item.prefix;
                }
                result += item.value;
                if (item.hasOwnProperty('suffix')) {
                    result += item.suffix;
                }

            }
            return result;
        }).join('');
    }

    function generateTweetPreview() {

        var addShortPermalink = function(classified) {
            classified.push({
                type: 'url',
                required: true,
                value: 'http://kyl.im/XXXXX',
                prefix: '\n(',
                suffix: ')'});
        };

        var addPermalink = function(classified) {
            classified.push({
                type: 'url',
                required: true,
                prefix: ' ',
                value: 'http://kylewm.com/XXXX/XX/XX/X'
            });
        };

        var target = 140;
        var titleField = $('#title'), contentArea = $('#content');

        var fullText, useShortPermalink;
        if (titleField.length > 0) {
            fullText = titleField.val();
            useShortPermalink = false;
        } else {
            fullText = contentArea.val();
            useShortPermalink = true;
        }

        var classified = classifyText(fullText);

        if (useShortPermalink) {
            addShortPermalink(classified);
        } else {
            addPermalink(classified);
        }

        if (estimateLength(classified) > target) {
            if (useShortPermalink) {
                // replace the shortlink with a full one
                classified.pop();
                addPermalink(classified);
            }
            shorten(classified, target);
        }

        var shortened = classifiedToString(classified);
        $('#tweet_preview').val(shortened);
        fillCharCount();
    }

    function fillCharCount() {
        var text = $('#tweet_preview').val();
        var classified = classifyText(text);
        var length = estimateLength(classified);
        $("#char_count").text(length);
    }

    /* register events */
    $(document).ready(function() {
        $('#uploads_link').click(function(event) {
            event.preventDefault();
            var left = (screen.width-100) / 2;
            var top = (screen.height-100) / 2;

            window.open('/admin/uploads', 'width=100,height=100,top='+top+',left='+left);
        });

        $('#save_draft_button').click(function(event) {
            clearResults();
            appendResult("Started save at: " + new Date($.now()).toTimeString());
            save(true);
        });

        $('#publish_button').click(function(event) {
            clearResults();
            appendResult("Started publish at: " + new Date($.now()).toTimeString());
            save(false);
        });

        var titleField = $('#title'), contentArea = $('#content');
        if (titleField.length != 0) {
            titleField.on('input propertychange', generateTweetPreview);
        } else {
            contentArea.on('input propertychange', generateTweetPreview);
        }

        $('#tweet_preview').on('input propertychange', fillCharCount);

        $("#get_coords_button").click(function() {
            navigator.geolocation.getCurrentPosition(function(position) {
                console.log(position);
                $("#latitude").val(position.coords.latitude.toFixed(3));
                $("#longitude").val(position.coords.longitude.toFixed(3));
            });
        });

        $("#image_upload_button").change(function() {
            var file = this.files[0];
            $('#result').append("<li>uploading file " + file.name + "</li>");

            if (undefined != file) {
                var formData = new FormData();
                formData.append('file', file);

                $.ajax({
                    url: '/api/upload_file',
                    type: 'POST',
                    success: uploadCompleteHandler,
                    error: uploadErrorHandler,
                    data: formData,
                    cache: false,
                    contentType: false,
                    processData: false
                });
            }
        });

        generateTweetPreview();
    });

})();
