$(document).ready(function () {
    const loadVideos = (page = 1) => {
        const query = new URLSearchParams(window.location.search).get('query') || '';
        $.ajax({
            url: '/api/videos',
            data: { page, query },
            success: function (data) {
                const videoContainer = $('#video-container');
                videoContainer.empty();
                data.videos.forEach(video => {
                    videoContainer.append(`
                        <div class="video-card">
                            <a href="/${video.display_title}/${video.file_code}">
                                <div class="video-thumbnail" style="background-image: url('${video.single_img}');" loading="lazy">
                                    <span class="video-duration">${video.length_formatted}</span>
                                </div>
                                <div class="video-info">
                                    <p class="video-title">${video.display_title}</p>
                                    <p class="video-date">${video.uploaded}</p>
                                </div>
                            </a>
                        </div>
                    `);
                });

                const pagination = $('#pagination');
                pagination.empty();
                if (data.total_pages > 1) {
                    if (data.current_page > 1) {
                        pagination.append(`<a href="#" class="page-link" data-page="${data.current_page - 1}">&laquo;</a>`);
                    }
                    data.pages.forEach(page => {
                        pagination.append(`<a href="#" class="page-link ${page === data.current_page ? 'active' : ''}" data-page="${page}">${page}</a>`);
                    });
                    if (data.current_page < data.total_pages) {
                        pagination.append(`<a href="#" class="page-link" data-page="${data.current_page + 1}">&raquo;</a>`);
                    }
                }
            },
            error: function () {
                alert('Failed to load videos');
            }
        });
    };

    $(document).on('click', '.page-link', function (e) {
        e.preventDefault();
        const page = $(this).data('page');
        loadVideos(page);
    });

    loadVideos();
});
