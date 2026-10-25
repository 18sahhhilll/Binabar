/**
 * Admin enhancement script for Song changelist and changeform
 */
document.addEventListener('DOMContentLoaded', function () {
    'use strict';

    var titleInput = document.getElementById('id_title');
    var artistInput = document.getElementById('id_artist');
    var yearInput = document.getElementById('id_year');
    var langInput = document.getElementById('id_language');

    var hintArtist = document.getElementById('id_hint_artist_initial');
    var hintYear = document.getElementById('id_hint_year');
    var hintLang = document.getElementById('id_hint_language');

    var ytInput = document.getElementById('id_youtube_id');
    var startInput = document.getElementById('id_start_seconds');
    var endInput = document.getElementById('id_end_seconds');

    var answersInput = document.getElementById('id_accepted_answers');

    // 1. YouTube ID auto-extractor
    if (ytInput) {
        ytInput.addEventListener('input', function () {
            var val = ytInput.value.trim();
            if (val.length > 11) {
                var m = val.match(/(?:youtube\.com\/(?:watch\?v=|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/);
                if (m && m[1]) {
                    ytInput.value = m[1];
                }
            }
            updateClipPreview();
        });
    }

    // 2. Auto-fill hints from primary fields
    if (artistInput && hintArtist) {
        artistInput.addEventListener('input', function () {
            if (!hintArtist.value && artistInput.value.trim()) {
                hintArtist.value = artistInput.value.trim().charAt(0).toUpperCase();
            }
        });
    }

    if (yearInput && hintYear) {
        yearInput.addEventListener('input', function () {
            if (!hintYear.value && yearInput.value.trim()) {
                hintYear.value = yearInput.value.trim();
            }
        });
    }

    if (langInput && hintLang) {
        langInput.addEventListener('input', function () {
            if (!hintLang.value && langInput.value.trim()) {
                hintLang.value = langInput.value.trim();
            }
        });
    }

    // 3. Clip duration warning indicator
    var durationBox = document.createElement('div');
    durationBox.id = 'clip-duration-indicator';
    if (endInput && endInput.parentNode) {
        endInput.parentNode.appendChild(durationBox);
    }

    function updateClipPreview() {
        if (!startInput || !endInput) return;
        var start = parseFloat(startInput.value) || 0;
        var end = parseFloat(endInput.value) || 0;
        var diff = end - start;

        if (end > 0) {
            var isValid = diff >= 8 && diff <= 20;
            durationBox.className = 'clip-duration-badge ' + (isValid ? 'valid' : 'invalid');
            durationBox.textContent = 'Clip Duration: ' + diff.toFixed(1) + 's ' +
                (isValid ? '(Valid: 8 to 20s)' : '(WARNING: Must be between 8 and 20s)');
        } else {
            durationBox.textContent = '';
        }
    }

    if (startInput) startInput.addEventListener('input', updateClipPreview);
    if (endInput) endInput.addEventListener('input', updateClipPreview);
    updateClipPreview();

    // 4. Suggest Accepted Answers Button
    if (titleInput && answersInput && answersInput.parentNode) {
        var suggestBtn = document.createElement('button');
        suggestBtn.type = 'button';
        suggestBtn.textContent = 'Suggest accepted answers from title';
        suggestBtn.style.cssText = 'margin-top: 6px; padding: 4px 10px; background: #333; color: #facc15; border: 1px solid #555; cursor: pointer; border-radius: 3px; font-size: 12px;';
        
        suggestBtn.addEventListener('click', function () {
            var title = titleInput.value.trim();
            if (!title) return;

            var suggestions = [];
            suggestions.push(title);

            // Remove content in brackets/parentheses
            var noBrackets = title.replace(/\s*[\(\[\{].*?[\)\]\}]\s*/g, ' ').trim();
            if (noBrackets && noBrackets !== title) {
                suggestions.push(noBrackets);
            }

            // Remove "feat." / "ft."
            var featRemoved = title.split(/\s+(?:feat\.?|ft\.?)\s+/i)[0].trim();
            if (featRemoved && featRemoved !== title) {
                suggestions.push(featRemoved);
            }

            // Remove punctuation
            var noPunct = title.replace(/[^\w\s]/g, '').trim();
            if (noPunct && noPunct !== title) {
                suggestions.push(noPunct);
            }

            var curr = answersInput.value.trim();
            var existing = [];
            if (curr.startsWith('[') && curr.endsWith(']')) {
                try {
                    existing = JSON.parse(curr);
                } catch (e) {
                    existing = curr.split(',').map(function (s) { return s.trim(); });
                }
            } else if (curr) {
                existing = curr.split(',').map(function (s) { return s.trim(); });
            }

            suggestions.forEach(function (s) {
                if (existing.indexOf(s) === -1) {
                    existing.push(s);
                }
            });

            answersInput.value = JSON.stringify(existing);
        });

        answersInput.parentNode.appendChild(suggestBtn);
    }
});
