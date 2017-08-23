package com.after_sunrise.cryptocurrency.cryptowelder.common;

import com.after_sunrise.cryptocurrency.cryptowelder.Cryptowelder;
import com.google.inject.AbstractModule;
import com.google.inject.Inject;
import com.google.inject.Injector;
import lombok.extern.slf4j.Slf4j;

import java.util.concurrent.CountDownLatch;

/**
 * @author takanori.takase
 * @version 0.0.1
 */
@Slf4j
public class CryptowelderImpl implements Cryptowelder {

    public static class Module extends AbstractModule {

        private final CountDownLatch latch = new CountDownLatch(1);

        @Override
        protected void configure() {

            bind(CountDownLatch.class).toInstance(latch);

            bind(Cryptowelder.class).to(CryptowelderImpl.class);

        }

    }

    private final Injector injector;

    @Inject
    public CryptowelderImpl(Injector injector) {
        this.injector = injector;
    }

    @Override
    public void run() {

        log.info("Running.");


    }

    @Override
    public void close() throws Exception {

        log.info("Terminating.");

        injector.getInstance(CountDownLatch.class).countDown();

    }

}
