using System;
using System.Buffers.Binary;
using System.IO;
using System.Security.Cryptography;
using System.Text;

namespace Wha.CaptureHost;

public sealed class StreamDigestCalculator : IDisposable
{
    private readonly IncrementalHash _hasher;
    private readonly ulong _startedMonotonicNs;

    public StreamDigestCalculator(
        string captureConfigHash,
        ulong width,
        ulong height,
        ulong targetFpsNumerator,
        ulong targetFpsDenominator,
        ulong startedMonotonicNs)
    {
        _startedMonotonicNs = startedMonotonicNs;
        _hasher = IncrementalHash.CreateHash(HashAlgorithmName.SHA256);

        // Header: UTF-8("whole-home-agent.capture-stream.v1\0")
        _hasher.AppendData(Encoding.UTF8.GetBytes("whole-home-agent.capture-stream.v1\0"));
        _hasher.AppendData(Convert.FromHexString(captureConfigHash));

        Span<byte> u64Buf = stackalloc byte[8];

        BinaryPrimitives.WriteUInt64BigEndian(u64Buf, width);
        _hasher.AppendData(u64Buf);

        BinaryPrimitives.WriteUInt64BigEndian(u64Buf, height);
        _hasher.AppendData(u64Buf);

        BinaryPrimitives.WriteUInt64BigEndian(u64Buf, targetFpsNumerator);
        _hasher.AppendData(u64Buf);

        BinaryPrimitives.WriteUInt64BigEndian(u64Buf, targetFpsDenominator);
        _hasher.AppendData(u64Buf);

        _hasher.AppendData(Encoding.UTF8.GetBytes("rgb24\0"));
    }

    public void UpdateFrame(ulong sourceSequence, ulong capturedMonotonicNs, ReadOnlySpan<byte> rgbBytes)
    {
        Span<byte> header = stackalloc byte[1 + 8 + 8 + 8];
        header[0] = 0x46; // 'F'
        BinaryPrimitives.WriteUInt64BigEndian(header.Slice(1, 8), sourceSequence);
        BinaryPrimitives.WriteUInt64BigEndian(header.Slice(9, 8), capturedMonotonicNs - _startedMonotonicNs);
        BinaryPrimitives.WriteUInt64BigEndian(header.Slice(17, 8), (ulong)rgbBytes.Length);

        _hasher.AppendData(header);
        _hasher.AppendData(rgbBytes);
    }

    public void UpdateGap(ulong firstMissing, ulong lastMissing, ulong detectedMonotonicNs, byte reasonCode)
    {
        Span<byte> gapBuf = stackalloc byte[1 + 8 + 8 + 8 + 1];
        gapBuf[0] = 0x47; // 'G'
        BinaryPrimitives.WriteUInt64BigEndian(gapBuf.Slice(1, 8), firstMissing);
        BinaryPrimitives.WriteUInt64BigEndian(gapBuf.Slice(9, 8), lastMissing);
        BinaryPrimitives.WriteUInt64BigEndian(gapBuf.Slice(17, 8), detectedMonotonicNs - _startedMonotonicNs);
        gapBuf[25] = reasonCode;

        _hasher.AppendData(gapBuf);
    }

    public string FinalizeHex()
    {
        byte[] hash = _hasher.GetHashAndReset();
        return Convert.ToHexString(hash).ToLowerInvariant();
    }

    public void Dispose()
    {
        _hasher.Dispose();
    }
}
