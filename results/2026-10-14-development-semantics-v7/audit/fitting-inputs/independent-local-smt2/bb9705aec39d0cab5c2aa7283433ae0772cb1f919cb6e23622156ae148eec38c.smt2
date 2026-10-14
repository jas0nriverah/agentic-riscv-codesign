(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x48 (bvadd independent_opaque_0 (bvadd (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32))) (_ bv3328 32)))))
(let ((?x67 (bvadd independent_opaque_0 (bvshl (bvadd independent_opaque_1 (_ bv832 32)) (bvand (_ bv2 32) (_ bv31 32))))))
(and (distinct ?x67 ?x48) true))))
(check-sat)
