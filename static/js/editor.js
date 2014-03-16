
(function() {

    $('#uploads_link').click(function(event) {
        event.preventDefault();
        var left = (screen.width-100) / 2;
        var top = (screen.height-100) / 2;

        window.open('/admin/uploads', 'width=100,height=100,top='+top+',left='+left);
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

                if (draft) {
                    addPermalink(data.id, data.permalink);
                } else {
                    syndicateToTwitter(data.id, data.permalink);
                }
            },
            error: function saveError(data) {
                appendResult("Failed to save post " + data.error);
            }
        });
    }

    function syndicateToTwitter(id, permalink) {
        var callback = syndicateToFacebook

        if ($("#send_to_twitter").prop("checked")) {
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
                    callback(id, permalink);
                },
                error:  function tweetFailure(data) {
                    appendResult("Failure " + data.error);
                    callback(id, permalink);
                }
            });

        } else {
            callback(id, permalink);
        }
    }

    function syndicateToFacebook(id, permalink) {
        var callback = sendWebmentions;

        if ($("#send_to_facebook").prop("checked")) {
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
                    callback(id, permalink);
                },
                error: function fbError(data) {
                    appendResult("Failure " + data.error);
                    callback(id, permalink);
                }

            });
        } else {
            callback(id, permalink);
        }

    }

    function sendWebmentions(id, permalink) {
        var callback = sendPushNotification;

        if ($("#send_webmentions").prop("checked")) {
            appendResult("Sending Webmentions");
            $.ajax({
                type: "POST",
                url: "/api/send_webmentions",
                data: {"post_id": id },
                success: function wmSuccess(data) {
                    if (data.success) {
                        appendResult("Success");
                        $.each(data.results, function (result) {
                            if (result.success) {
                                appendResult("Sent to " + result.target);
                            } else {
                                appendResult("Failure for " + result.target + ", " + result.explanation);
                            }
                        });
                    } else {
                        appendResult("Failure: " + data.error);
                    }
                    callback(id, permalink);
                },
                error: function wmFailure(data) {
                    appendResult("Failure: " + data.error);
                    callback(id, permalink);
                }
            });
        } else {
            callback(id, permalink);
        }

    }

    function sendPushNotification(id, permalink) {
        callback = addPermalink;

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
                callback(id, permalink);
            },
            error: function pushError(data) {
                appendResult("Failure: " + data.error);
                callback(id, permalink);
            }
        });
    }

    function addPermalink(id, permalink) {
        appendResult("<a href=" + permalink + ">View Post</a>");
        appendResult("Done at " + new Date($.now()).toTimeString());

        //$('#preview').css('display', 'block');
        //$('#preview').attr('src', '/admin/preview?id=' + id);
    }

    function appendResult(str) {
        $('#result').append("<li>" + str + "</li>");
    }


    $('#save_draft_button').click(function(event) {
        clearResults();
        appendResult("Started save at: " + new Date($.now()).toTimeString());
        save(true, addPermalink);
    });

    $('#publish_button').click(function(event) {
        clearResults();
        appendResult("Started publish at: " + new Date($.now()).toTimeString());
        save(false, syndicateToTwitter);
    });


})();
