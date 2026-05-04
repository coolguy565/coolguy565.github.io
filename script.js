const files = [
    {
        url: "https://raw.githubusercontent.com/zulofileuploadservicev2/zulofileuploadservicev2.github.io/refs/heads/main/files/test.txt",
        description: "test text file hosted on github"
    },
    {
        url: "https://raw.githubusercontent.com/zulofileuploadservicev2/zulofileuploadservicev2.github.io/refs/heads/main/files/Tools%20you%20should%20put%20on%20myusb.zip",
        description: "usb tools for collabvm"
    }
];

const fileList = document.getElementById('file-list');
const fileCount = document.getElementById('file-count');
const searchInput = document.getElementById('search-input');

fileCount.textContent = files.length;

function formatFileSize(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

function getFileExtension(filename) {
    return filename.split('.').pop().toLowerCase();
}

function getFileIcon(ext) {
    const icons = {
        txt: '<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>',
        pdf: '<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>',
        zip: '<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>'
    };
    return icons[ext] || icons.txt;
}

function downloadFile(url, filename, progressBar, statusText, progressContainer) {
    const xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.responseType = 'blob';

    progressContainer.style.display = 'flex';
    progressBar.style.display = 'block';
    statusText.style.display = 'block';

    xhr.onprogress = (event) => {
        if (event.lengthComputable) {
            const percentComplete = (event.loaded / event.total) * 100;
            progressBar.value = percentComplete;
            const elapsedTime = (Date.now() - xhr.startTime) / 1000;
            const averageSpeed = event.loaded / elapsedTime;
            const bytesRemaining = event.total - event.loaded;
            const secondsRemaining = Math.round(bytesRemaining / averageSpeed);
            statusText.textContent = `${Math.round(percentComplete)}% · ${secondsRemaining}s remaining · ${formatFileSize(averageSpeed)}/s`;
        }
    };

    xhr.onloadstart = () => {
        xhr.startTime = Date.now();
    };

    xhr.onload = () => {
        if (xhr.status === 200) {
            const blob = xhr.response;
            const objectUrl = window.URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.href = objectUrl;
            link.download = filename;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
            window.URL.revokeObjectURL(objectUrl);

            setTimeout(() => {
                progressContainer.style.display = 'none';
                progressBar.style.display = 'none';
                statusText.style.display = 'none';
                progressBar.value = 0;
            }, 500);
        }
    };

    xhr.onerror = () => {
        statusText.textContent = 'Download failed';
        statusText.style.color = '#ef4444';
        setTimeout(() => {
            progressContainer.style.display = 'none';
            progressBar.style.display = 'none';
            statusText.style.display = 'none';
            statusText.style.color = '';
        }, 3000);
    };

    xhr.send();
}

function createFileElement(file) {
    const li = document.createElement('li');
    const filename = decodeURIComponent(file.url.split('/').pop());
    const ext = getFileExtension(filename);

    li.innerHTML = `
        <div class="file-info">
            <div class="file-name" data-url="${file.url}">
                <div class="file-icon">${getFileIcon(ext)}</div>
                <span>${filename}</span>
            </div>
            <small class="file-description">${file.description}</small>
        </div>
        <div class="file-meta">
            <div class="progress-container" style="display:none; width:100%;">
                <progress class="progress-bar" max="100" value="0"></progress>
                <span class="status-text"></span>
            </div>
            <button class="download-btn">download</button>
        </div>
    `;

    const fileNameEl = li.querySelector('.file-name');
    const downloadBtn = li.querySelector('.download-btn');
    const progressBar = li.querySelector('.progress-bar');
    const statusText = li.querySelector('.status-text');
    const progressContainer = li.querySelector('.progress-container');

    const handleDownload = (e) => {
        e.preventDefault();
        e.stopPropagation();
        downloadFile(file.url, filename, progressBar, statusText, progressContainer);
    };

    fileNameEl.addEventListener('click', handleDownload);
    downloadBtn.addEventListener('click', handleDownload);

    return li;
}

function renderFiles(filter = '') {
    fileList.innerHTML = '';
    const filtered = files.filter(f => 
        f.url.toLowerCase().includes(filter.toLowerCase()) ||
        f.description.toLowerCase().includes(filter.toLowerCase())
    );

    if (filtered.length === 0) {
        fileList.innerHTML = '<li style="text-align:center;padding:2rem;color:var(--text-muted);">no files found</li>';
        return;
    }

    filtered.forEach(file => {
        fileList.appendChild(createFileElement(file));
    });
}

renderFiles();

searchInput.addEventListener('input', (e) => {
    renderFiles(e.target.value);
});
