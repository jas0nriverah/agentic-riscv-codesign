(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x74 (bvadd independent_opaque_0 (bvadd (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32))) (_ bv4294967292 32)))))
(let ((?x409 (bvadd independent_opaque_0 (bvshl (bvadd independent_opaque_1 (_ bv4294967295 32)) (bvand (_ bv2 32) (_ bv31 32))))))
(and (distinct ?x409 ?x74) true))))
(check-sat)
