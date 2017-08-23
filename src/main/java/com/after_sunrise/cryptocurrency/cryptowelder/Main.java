package com.after_sunrise.cryptocurrency.cryptowelder;

import com.google.inject.AbstractModule;
import com.google.inject.Guice;
import com.google.inject.Module;
import lombok.extern.slf4j.Slf4j;

/**
 * @author takanori.takase
 * @version 0.0.1
 */
@Slf4j
public class Main extends AbstractModule implements Cryptowelder {

    public static final String MODULE = "cryptowelder.module";

    public static void main(String... args) throws Exception {

        String moduleName = System.getProperty(MODULE, Main.class.getName());

        Module module = (Module) Class.forName(moduleName).newInstance();

        log.info("Starting application : {}", moduleName);

        Cryptowelder application = Guice.createInjector(module).getInstance(Cryptowelder.class);

        try {

            application.run();

        } finally {

            application.close();

        }

        log.info("Stopped application.");

    }

    @Override
    protected void configure() {

        bind(Cryptowelder.class).toInstance(this);

    }

    @Override
    public void run() {

        log.info("Run.");

    }

    @Override
    public void close() throws Exception {

        log.info("Close.");

    }

}
