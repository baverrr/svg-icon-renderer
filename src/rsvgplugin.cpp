// glib/gio headers use `signals` as a field name, so they go first and the build sets QT_NO_KEYWORDS.
#include <cairo.h>
#include <librsvg/rsvg.h>

#include "rsvgplugin.h"

#include <QIODevice>
#include <QImage>
#include <QLoggingCategory>
#include <QVariant>
#include <cmath>

Q_LOGGING_CATEGORY(lcRsvg, "rsvgqt", QtWarningMsg)

// Used when a file has neither width/height nor a viewBox; matches QtSvg's fallback.
static const QSizeF kFallbackSize(100, 100);

static RsvgHandle *rsvg(void *p)
{
    return static_cast<RsvgHandle *>(p);
}

RsvgHandler::~RsvgHandler()
{
    if (m_handle)
        g_object_unref(m_handle);
}

bool RsvgHandler::canRead(QIODevice *device)
{
    if (!device)
        return false;
    const QByteArray head = device->peek(4096);
    if (head.startsWith("\x1f\x8b")) // gzip, i.e. svgz
        return true;
    return head.contains("<svg") || head.contains("<!DOCTYPE svg");
}

bool RsvgHandler::canRead() const
{
    if (m_loaded)
        return !m_failed;
    if (canRead(device())) {
        setFormat(device()->peek(2).startsWith("\x1f\x8b") ? "svgz" : "svg");
        return true;
    }
    return false;
}

bool RsvgHandler::load()
{
    if (m_loaded)
        return !m_failed;
    m_loaded = true;
    m_failed = true;
    if (!device())
        return false;

    const QByteArray data = device()->readAll();
    if (data.isEmpty())
        return false;

    // No base file is set, so the document can't pull in external files; data: URIs still work.
    // librsvg detects and inflates gzip (svgz) data by itself.
    GError *error = nullptr;
    RsvgHandle *handle = rsvg_handle_new_from_data(reinterpret_cast<const guint8 *>(data.constData()),
                                                   gsize(data.size()), &error);
    if (!handle) {
        qCWarning(lcRsvg) << "parse failed:" << (error ? error->message : "unknown error");
        g_clear_error(&error);
        return false;
    }
    m_handle = handle;
    rsvg_handle_set_dpi(handle, 96.0);

    gdouble w = 0, h = 0;
    if (rsvg_handle_get_intrinsic_size_in_pixels(handle, &w, &h) && w > 0 && h > 0) {
        m_intrinsic = QSizeF(w, h);
    } else {
        gboolean hasW, hasH, hasViewBox;
        RsvgLength lw, lh;
        RsvgRectangle viewBox;
        rsvg_handle_get_intrinsic_dimensions(handle, &hasW, &lw, &hasH, &lh, &hasViewBox, &viewBox);
        m_intrinsic = (hasViewBox && viewBox.width > 0 && viewBox.height > 0)
            ? QSizeF(viewBox.width, viewBox.height)
            : kFallbackSize;
    }
    m_failed = false;
    return true;
}

bool RsvgHandler::read(QImage *image)
{
    if (!load())
        return false;

    const QSize size = m_scaledSize.isValid() ? m_scaledSize
                                              : QSize(qMax(1, qRound(m_intrinsic.width())),
                                                      qMax(1, qRound(m_intrinsic.height())));
    QImage out;
    // allocateImage enforces QImageReader's allocation limit, so a huge requested size fails instead of eating memory.
    if (!QImageIOHandler::allocateImage(size, QImage::Format_ARGB32_Premultiplied, &out))
        return false;
    out.fill(Qt::transparent);

    // Cairo's ARGB32 is native-endian premultiplied, the same layout as Qt's ARGB32_Premultiplied.
    cairo_surface_t *surface = cairo_image_surface_create_for_data(out.bits(), CAIRO_FORMAT_ARGB32,
                                                                   out.width(), out.height(),
                                                                   int(out.bytesPerLine()));
    cairo_t *cr = cairo_create(surface);
    // Stretch the document to the requested size like QtSvg does, rather than letterboxing it.
    cairo_scale(cr, out.width() / m_intrinsic.width(), out.height() / m_intrinsic.height());
    const RsvgRectangle viewport = {0, 0, m_intrinsic.width(), m_intrinsic.height()};
    GError *error = nullptr;
    const bool ok = rsvg_handle_render_document(rsvg(m_handle), cr, &viewport, &error);
    cairo_destroy(cr);
    cairo_surface_finish(surface);
    cairo_surface_destroy(surface);

    if (!ok) {
        qCWarning(lcRsvg) << "render failed:" << (error ? error->message : "unknown error");
        g_clear_error(&error);
        return false;
    }
    *image = std::move(out);
    return true;
}

QVariant RsvgHandler::option(ImageOption option) const
{
    switch (option) {
    case Size:
        if (const_cast<RsvgHandler *>(this)->load())
            return QSize(qMax(1, qRound(m_intrinsic.width())), qMax(1, qRound(m_intrinsic.height())));
        return QVariant();
    case ScaledSize:
        return m_scaledSize;
    case ImageFormat:
        return QImage::Format_ARGB32_Premultiplied;
    default:
        return QVariant();
    }
}

void RsvgHandler::setOption(ImageOption option, const QVariant &value)
{
    if (option == ScaledSize)
        m_scaledSize = value.toSize();
}

bool RsvgHandler::supportsOption(ImageOption option) const
{
    return option == Size || option == ScaledSize || option == ImageFormat;
}

QImageIOPlugin::Capabilities RsvgPlugin::capabilities(QIODevice *device, const QByteArray &format) const
{
    if (format == "svg" || format == "svgz")
        return CanRead;
    if (!format.isEmpty())
        return {};
    if (device && device->isReadable() && RsvgHandler::canRead(device))
        return CanRead;
    return {};
}

QImageIOHandler *RsvgPlugin::create(QIODevice *device, const QByteArray &format) const
{
    auto *handler = new RsvgHandler;
    handler->setDevice(device);
    handler->setFormat(format);
    return handler;
}
