(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x34 (bvadd independent_opaque_0 (bvadd (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32))) (_ bv4294967295 32)))))
(let ((?x1104 (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x329 (bvadd (bvadd independent_opaque_0 (_ bv4294967295 32)) ?x1104)))
(and (distinct ?x329 ?x34) true)))))
(check-sat)
