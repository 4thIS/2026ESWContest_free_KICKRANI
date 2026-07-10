package com.vibrasoft.kickboardapp

import android.os.Bundle
import android.view.Menu
import android.view.MenuItem
import androidx.appcompat.app.AppCompatActivity
import androidx.navigation.NavController
import androidx.navigation.fragment.NavHostFragment
import androidx.navigation.ui.setupWithNavController
import com.vibrasoft.kickboardapp.bluetooth.BluetoothConnector
import com.vibrasoft.kickboardapp.bluetooth.RpiProtocol
import com.vibrasoft.kickboardapp.databinding.ActivityMainBinding
import com.vibrasoft.kickboardapp.ui.SettingsBottomSheet

class MainActivity : AppCompatActivity() {
    private lateinit var binding: ActivityMainBinding
    private lateinit var navController: NavController

    lateinit var bluetoothConnector: BluetoothConnector
        private set
    lateinit var rpiProtocol: RpiProtocol
        private set

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)

        bluetoothConnector = BluetoothConnector(this)
        rpiProtocol = RpiProtocol(bluetoothConnector)

        val navHost = supportFragmentManager
            .findFragmentById(R.id.nav_host_fragment) as NavHostFragment
        navController = navHost.navController
        binding.bottomNav.setupWithNavController(navController)
    }

    override fun onCreateOptionsMenu(menu: Menu): Boolean {
        menuInflater.inflate(R.menu.main_toolbar_menu, menu)
        return true
    }

    override fun onOptionsItemSelected(item: MenuItem): Boolean {
        if (item.itemId == R.id.action_settings) {
            SettingsBottomSheet().show(supportFragmentManager, "settings")
            return true
        }
        return super.onOptionsItemSelected(item)
    }

    override fun onDestroy() {
        super.onDestroy()
        rpiProtocol.stopListening()
        bluetoothConnector.disconnect()
    }
}
