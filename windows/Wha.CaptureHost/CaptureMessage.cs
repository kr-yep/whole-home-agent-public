using System;
using System.Buffers.Binary;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace Wha.CaptureHost;

public static class CaptureProtocolConstants
{
    public static readonly byte[] Magic = Encoding.ASCII.GetBytes("WHA1");
    public const byte WireVersion = 1;
    public const byte KindStart = 1;
    public const byte KindFrame = 2;
    public const byte KindGap = 3;
    public const byte KindEnd = 4;
    public const int FixedPrefixBytes = 16;
    public const int FrameBodyBytes = 2764800; // 1280 * 720 * 3
}

public readonly struct WirePrefix
{
    public byte WireVersion { get; }
    public byte MessageKind { get; }
    public ushort Flags { get; }
    public uint MetadataLength { get; }
    public uint BodyLength { get; }

    public WirePrefix(byte messageKind, uint metadataLength, uint bodyLength)
    {
        WireVersion = CaptureProtocolConstants.WireVersion;
        MessageKind = messageKind;
        Flags = 0;
        MetadataLength = metadataLength;
        BodyLength = bodyLength;
    }

    public void WriteTo(Span<byte> destination)
    {
        CaptureProtocolConstants.Magic.CopyTo(destination[..4]);
        destination[4] = WireVersion;
        destination[5] = MessageKind;
        BinaryPrimitives.WriteUInt16BigEndian(destination.Slice(6, 2), Flags);
        BinaryPrimitives.WriteUInt32BigEndian(destination.Slice(8, 4), MetadataLength);
        BinaryPrimitives.WriteUInt32BigEndian(destination.Slice(12, 4), BodyLength);
    }
}
