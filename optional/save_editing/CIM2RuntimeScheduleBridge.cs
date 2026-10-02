// Optional in-process helper source. Build/load only in an isolated CIM2 test
// profile. This file is never copied into the live game installation by the
// Python application.
using System;
using System.IO;
using System.Reflection;

namespace CIM2SaveStats.RuntimeBridge
{
    public static class ScheduleBridgeContract
    {
        public const string Protocol = "cim2-schedule-bridge/1";

        // The host must call this only after the game has loaded the input
        // through GameState.LoadFromFile. No binary payload is fabricated here.
        public static string SaveLoadedState(object gameState, string outputPath)
        {
            if (gameState == null) throw new ArgumentNullException("gameState");
            if (String.IsNullOrWhiteSpace(outputPath)) throw new ArgumentException("outputPath");
            string full = Path.GetFullPath(outputPath);
            MethodInfo save = gameState.GetType().GetMethod("SaveToFile",
                BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic,
                null, new[] { typeof(string) }, null);
            if (save == null) throw new MissingMethodException("GameState.SaveToFile(string)");
            Directory.CreateDirectory(Path.GetDirectoryName(full));
            object result = save.Invoke(gameState, new object[] { full });
            if (!File.Exists(full) || new FileInfo(full).Length == 0)
                throw new IOException("GameState.SaveToFile did not create output");
            return result == null ? String.Empty : Convert.ToString(result);
        }
    }
}
