(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun y () (_ BitVec 32))
(declare-fun x () (_ BitVec 32))
(assert
 (let ((?x191 (bvshl y (_ bv16 32))))
(let ((?x187 (bvshl x (_ bv16 32))))
(let ((?x192 (bvadd ?x187 ?x191)))
(let ((?x19 (bvadd x y)))
(let ((?x190 (bvshl ?x19 (_ bv16 32))))
(and (distinct ?x190 ?x192) true)))))))
(check-sat)
