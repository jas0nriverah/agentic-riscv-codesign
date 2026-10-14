(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x40 (bvadd independent_opaque_0 (bvadd independent_opaque_1 (_ bv4294967292 32)))))
(let ((?x50 (bvadd (bvadd independent_opaque_0 (_ bv4294967292 32)) independent_opaque_1)))
(and (distinct ?x50 ?x40) true))))
(check-sat)
