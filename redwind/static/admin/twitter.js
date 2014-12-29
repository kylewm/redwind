(function(global) {
    "use strict";

    var shortUrlLength = 22;
    var shortUrlLengthHttps = 23;
    var mediaUrlLength = 23;

    /* splits a text string into text and urls */
    function classifyText(text) {
        var result = [];

        var match;
        var lastIndex = 0;
        var urlRegex = /https?:\/\/[_a-zA-Z0-9.\/\-!#$%?:]+/g;
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
                var urlLength = item.value.startsWith('https') ?
                    shortUrlLengthHttps : shortUrlLength;
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
        var titleField = first('#title'), contentArea = first('#content');

        var fullText, useShortPermalink;
        if (titleField.length > 0) {
            fullText = titleField.value;
            useShortPermalink = false;
        } else {
            fullText = contentArea.value;
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
        first('#preview').value = shortened;
        fillCharCount();
    }

    function fillCharCount() {
        var preview = first('#preview');
        if (preview) {
            var classified = classifyText(preview.value);
            var length = estimateLength(classified);
            first('#char_count').textContent = length;
        }
    }

    var previewField = first('#preview');
    if (previewField) {
        previewField.addEventListener('input', fillCharCount);
    }
    each(all('#permalink, #permashortlink, #permashortcite'), function(el) {
        el.addEventListener('click', function() { select(); });
    });
    fillCharCount();

})(this);
