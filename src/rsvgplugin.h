// Qt image-format plugin that draws SVG/SVGZ with librsvg instead of QtSvg,
// so filters (blur, drop shadow, turbulence, lighting), masks and the rest of SVG 1.1 render.
#pragma once

#include <QImageIOHandler>
#include <QImageIOPlugin>
#include <QSize>

class RsvgHandler : public QImageIOHandler
{
public:
    ~RsvgHandler() override;

    bool canRead() const override;
    bool read(QImage *image) override;
    QVariant option(ImageOption option) const override;
    void setOption(ImageOption option, const QVariant &value) override;
    bool supportsOption(ImageOption option) const override;

    static bool canRead(QIODevice *device);

private:
    bool load();

    void *m_handle = nullptr; // RsvgHandle*, kept opaque so Qt code never sees glib headers
    bool m_loaded = false;
    bool m_failed = false;
    QSizeF m_intrinsic;
    QSize m_scaledSize;
};

class RsvgPlugin : public QImageIOPlugin
{
    Q_OBJECT
    Q_PLUGIN_METADATA(IID QImageIOHandlerFactoryInterface_iid FILE "rsvgplugin.json")

public:
    Capabilities capabilities(QIODevice *device, const QByteArray &format) const override;
    QImageIOHandler *create(QIODevice *device, const QByteArray &format = QByteArray()) const override;
};
