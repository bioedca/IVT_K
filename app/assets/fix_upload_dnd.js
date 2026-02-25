/**
 * Workaround for Dash 4.0 dcc.Upload multi-file drag-and-drop bug.
 *
 * Dash 4.0's Upload component uses an async getDataTransferItems() that calls
 * webkitGetAsEntry() inside a for-await loop.  After the first await boundary
 * the browser invalidates the remaining DataTransferItem references, so only
 * the first dragged file is captured.
 *
 * Strategy 1 (Chrome/Edge): Override dataTransfer.items via Object.defineProperty
 * so the component falls through to the synchronous dataTransfer.files path.
 *
 * Strategy 2 (Firefox/Safari fallback): If the property override fails or doesn't
 * apply, stop the event and manually read files + update the Dash component via
 * dash_clientside.set_props.
 */
(function () {
    if (window._uploadDropPatchApplied) return;
    window._uploadDropPatchApplied = true;

    document.addEventListener('drop', function (e) {
        var dropzone = document.getElementById('upload-dropzone');
        if (!dropzone || !dropzone.contains(e.target)) return;
        if (!e.dataTransfer || !e.dataTransfer.files || e.dataTransfer.files.length <= 1) return;

        // Strategy 1: neutralize dataTransfer.items so Dash falls through
        // to the synchronous dataTransfer.files path
        var overrideApplied = false;
        try {
            Object.defineProperty(e.dataTransfer, 'items', {
                get: function () { return null; },
                configurable: true,
            });
            overrideApplied = (e.dataTransfer.items === null);
        } catch (err) {
            // Property override not allowed on this browser
        }

        if (overrideApplied) return;

        // Strategy 2: intercept the event entirely and feed files to Dash
        // manually via dash_clientside.set_props (available since Dash 2.17)
        e.stopImmediatePropagation();
        e.preventDefault();

        var files = Array.from(e.dataTransfer.files);
        var contents = [];
        var filenames = [];
        var lastModified = [];
        var remaining = files.length;

        files.forEach(function (file) {
            var reader = new FileReader();
            reader.onload = function () {
                contents.push(reader.result);
                filenames.push(file.name);
                lastModified.push(file.lastModified / 1000);
                remaining--;
                if (remaining === 0 && window.dash_clientside && window.dash_clientside.set_props) {
                    window.dash_clientside.set_props('upload-dropzone', {
                        contents: contents,
                        filename: filenames,
                        last_modified: lastModified,
                    });
                }
            };
            reader.readAsDataURL(file);
        });
    }, true);  // capture phase — runs before react-dropzone's handler
})();
