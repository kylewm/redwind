
(function() {

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
    });


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

            $.ajax({
                type: "POST",
                url: "/api/syndicate_to_twitter",
                data: {"post_id": id },
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

    function appendResult(str) {
        $('#result').append("<li>" + str + "</li>");
    }



})();
